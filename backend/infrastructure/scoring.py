from __future__ import annotations

import math

from geometry import polygon_area_and_centroid
from schemas import (
    BoundingBox,
    CandidateRegion,
    Coordinate,
    DataCenterAssetSpec,
    DEFAULT_PANEL_AZIMUTH_DEG,
    DEFAULT_PANEL_TILT_DEG,
    SolarAssetSpec,
    WindAssetSpec,
)
from solar_project import (
    SolarProjectInputs,
    _estimate_panel_dimensions_from_area,
    analyze_solar_project,
)

from .common import clamp, pseudo, solar_irradiance_proxy, wind_speed_proxy
from .grid import (
    clip_polygon_to_bbox,
    nearest_road_distance_m,
    overlap_building_area_m2,
    overlap_water_area_m2,
)
from .models import BuildingFootprint, ImageryRaster, RoadFeature, WaterFeature
from .segmentation import proxy_landcover, sample_imagery_features


def _rect_polygon(
    bbox: BoundingBox,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> list[Coordinate]:
    lon_span = bbox.max_lon - bbox.min_lon
    lat_span = bbox.max_lat - bbox.min_lat
    return [
        Coordinate(
            lat=bbox.min_lat + lat_span * min_y,
            lon=bbox.min_lon + lon_span * min_x,
        ),
        Coordinate(
            lat=bbox.min_lat + lat_span * min_y,
            lon=bbox.min_lon + lon_span * max_x,
        ),
        Coordinate(
            lat=bbox.min_lat + lat_span * max_y,
            lon=bbox.min_lon + lon_span * max_x,
        ),
        Coordinate(
            lat=bbox.min_lat + lat_span * max_y,
            lon=bbox.min_lon + lon_span * min_x,
        ),
    ]


def _build_visual_solar_layout(
    valid_region_polygons: list[list[Coordinate]],
    valid_region_areas_m2: list[float],
    packed_usable_area_m2: float,
) -> tuple[list[list[Coordinate]], list[list[Coordinate]]]:
    packing_blocks: list[list[Coordinate]] = []
    total_valid_area_m2 = max(sum(valid_region_areas_m2), 1.0)
    for region_index, region in enumerate(valid_region_polygons):
        region_bbox = BoundingBox(
            min_lat=min(point.lat for point in region),
            min_lon=min(point.lon for point in region),
            max_lat=max(point.lat for point in region),
            max_lon=max(point.lon for point in region),
        )
        region_area_ratio = clamp(
            valid_region_areas_m2[region_index] / total_valid_area_m2,
            0.0,
            1.0,
        )
        packed_ratio = clamp(
            packed_usable_area_m2 / total_valid_area_m2,
            0.0,
            1.0,
        )
        cols = 3 if region_area_ratio > 0.2 else 2
        rows = 2 if region_area_ratio > 0.12 else 1
        block_margin_x = 0.08
        block_margin_y = 0.12
        usable_width = 1.0 - (block_margin_x * 2)
        usable_height = max(0.16, packed_ratio * clamp(region_area_ratio * 1.8, 0.35, 1.0))
        block_width = usable_width / cols
        block_height = usable_height / rows
        start_y = 0.12

        for row in range(rows):
            for col in range(cols):
                x0 = block_margin_x + col * block_width
                y0 = start_y + row * block_height
                x1 = x0 + block_width * 0.82
                y1 = y0 + block_height * 0.72
                packing_blocks.append(
                    _rect_polygon(region_bbox, x0, y0, x1, y1)
                )

    return valid_region_polygons, packing_blocks


def _build_box_layout_within_polygons(
    valid_region_polygons: list[list[Coordinate]],
    valid_region_areas_m2: list[float],
    item_count: int,
    item_area_m2: float,
    *,
    fill_ratio: float,
    min_rows: int = 1,
) -> list[list[Coordinate]]:
    if item_count <= 0 or item_area_m2 <= 0 or not valid_region_polygons:
        return []

    total_area_m2 = max(sum(valid_region_areas_m2), 1.0)
    remaining = item_count
    placements: list[list[Coordinate]] = []

    for region_index, region in enumerate(valid_region_polygons):
        if remaining <= 0:
            break
        region_area_ratio = clamp(valid_region_areas_m2[region_index] / total_area_m2, 0.0, 1.0)
        count_for_region = max(
            1,
            round(item_count * region_area_ratio),
        )
        count_for_region = min(count_for_region, remaining)
        remaining -= count_for_region

        region_bbox = BoundingBox(
            min_lat=min(point.lat for point in region),
            min_lon=min(point.lon for point in region),
            max_lat=max(point.lat for point in region),
            max_lon=max(point.lon for point in region),
        )
        cols = max(1, round(count_for_region ** 0.5))
        rows = max(min_rows, math.ceil(count_for_region / cols))
        margin_x = 0.06
        margin_y = 0.08
        usable_width = max(0.12, 1.0 - margin_x * 2)
        usable_height = max(0.16, 1.0 - margin_y * 2)
        slot_width = usable_width / cols
        slot_height = usable_height / rows

        for item_index in range(count_for_region):
            row = item_index // cols
            col = item_index % cols
            x0 = margin_x + col * slot_width
            y0 = margin_y + row * slot_height
            x1 = x0 + slot_width * fill_ratio
            y1 = y0 + slot_height * fill_ratio
            placements.append(_rect_polygon(region_bbox, x0, y0, x1, y1))

    return placements


def _project_point_to_local(
    point: Coordinate,
    *,
    origin_lat: float,
    origin_lon: float,
) -> tuple[float, float]:
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * max(0.25, math.cos(math.radians(origin_lat)))
    x = (point.lon - origin_lon) * lon_scale
    y = (point.lat - origin_lat) * lat_scale
    return x, y


def _unproject_point_from_local(
    x: float,
    y: float,
    *,
    origin_lat: float,
    origin_lon: float,
) -> Coordinate:
    lat_scale = 111_320.0
    lon_scale = 111_320.0 * max(0.25, math.cos(math.radians(origin_lat)))
    return Coordinate(
        lat=origin_lat + y / lat_scale,
        lon=origin_lon + x / lon_scale,
    )


def _rotate_xy(x: float, y: float, angle_rad: float) -> tuple[float, float]:
    cos_angle = math.cos(angle_rad)
    sin_angle = math.sin(angle_rad)
    return (
        x * cos_angle - y * sin_angle,
        x * sin_angle + y * cos_angle,
    )


def _point_in_polygon_xy(x: float, y: float, polygon_xy: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon_xy) - 1
    for i in range(len(polygon_xy)):
        xi, yi = polygon_xy[i]
        xj, yj = polygon_xy[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _dominant_polygon_angle(points: list[Coordinate], origin_lat: float, origin_lon: float) -> float:
    best_length = 0.0
    best_angle = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        x1, y1 = _project_point_to_local(point, origin_lat=origin_lat, origin_lon=origin_lon)
        x2, y2 = _project_point_to_local(next_point, origin_lat=origin_lat, origin_lon=origin_lon)
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length > best_length:
            best_length = length
            best_angle = math.atan2(dy, dx)
    return best_angle


def _pack_rectangles_in_polygon(
    polygon: list[Coordinate],
    *,
    rect_length_m: float,
    rect_width_m: float,
    max_rectangles: int | None,
    row_gap_m: float,
    col_gap_m: float,
) -> tuple[list[list[Coordinate]], int]:
    if (max_rectangles is not None and max_rectangles <= 0) or len(polygon) < 3:
        return [], 0

    origin_lat = sum(point.lat for point in polygon) / len(polygon)
    origin_lon = sum(point.lon for point in polygon) / len(polygon)
    polygon_xy = [
        _project_point_to_local(point, origin_lat=origin_lat, origin_lon=origin_lon)
        for point in polygon
    ]
    dominant_angle = _dominant_polygon_angle(polygon, origin_lat, origin_lon)
    orientations = [
        (dominant_angle, rect_length_m, rect_width_m),
        (dominant_angle, rect_width_m, rect_length_m),
        (dominant_angle + math.pi / 2.0, rect_length_m, rect_width_m),
        (dominant_angle + math.pi / 2.0, rect_width_m, rect_length_m),
    ]

    best_layout: list[list[Coordinate]] = []
    best_count = 0
    for angle, length_m, width_m in orientations:
        rotated_polygon = [_rotate_xy(x, y, -angle) for x, y in polygon_xy]
        min_x = min(x for x, _y in rotated_polygon)
        max_x = max(x for x, _y in rotated_polygon)
        min_y = min(y for _x, y in rotated_polygon)
        max_y = max(y for _x, y in rotated_polygon)
        step_x = width_m + col_gap_m
        step_y = length_m + row_gap_m

        layout: list[list[Coordinate]] = []
        layout_count = 0
        y = min_y
        while y + length_m <= max_y + 1e-6:
            x = min_x
            while x + width_m <= max_x + 1e-6:
                rotated_rect = [
                    (x, y),
                    (x + width_m, y),
                    (x + width_m, y + length_m),
                    (x, y + length_m),
                ]
                if all(_point_in_polygon_xy(rx, ry, rotated_polygon) for rx, ry in rotated_rect):
                    layout_count += 1
                    if max_rectangles is None or len(layout) < max_rectangles:
                        layout.append(
                            [
                                _unproject_point_from_local(
                                    *_rotate_xy(rx, ry, angle),
                                    origin_lat=origin_lat,
                                    origin_lon=origin_lon,
                                )
                                for rx, ry in rotated_rect
                            ]
                        )
                x += step_x
            y += step_y

        if layout_count > best_count:
            best_layout = layout
            best_count = layout_count

    return best_layout, best_count


def _build_solar_panel_placements(
    valid_region_polygons: list[list[Coordinate]],
    valid_region_areas_m2: list[float],
    panel_area_m2: float,
) -> tuple[list[list[Coordinate]], int, int]:
    if not valid_region_polygons or panel_area_m2 <= 0:
        return [], 0, 0

    panel_length_m, panel_width_m = _estimate_panel_dimensions_from_area(panel_area_m2)
    placements_by_region: list[list[list[Coordinate]]] = []
    counts_by_region: list[int] = []
    total_count = 0

    for region in valid_region_polygons:
        _sampled, packed_count = _pack_rectangles_in_polygon(
            region,
            rect_length_m=panel_length_m,
            rect_width_m=panel_width_m,
            max_rectangles=None,
            row_gap_m=max(0.2, panel_width_m * 0.15),
            col_gap_m=max(0.1, panel_length_m * 0.08),
        )
        counts_by_region.append(packed_count)
        total_count += packed_count

    if total_count <= 0:
        return [], 0, 0

    display_limit = min(total_count, 1500)
    total_area_m2 = max(sum(valid_region_areas_m2), 1.0)
    remaining = display_limit
    for region_index, region in enumerate(valid_region_polygons):
        if remaining <= 0:
            placements_by_region.append([])
            continue
        region_count = counts_by_region[region_index]
        if region_count <= 0:
            placements_by_region.append([])
            continue
        region_area_ratio = clamp(valid_region_areas_m2[region_index] / total_area_m2, 0.0, 1.0)
        count_for_region = max(1, round(display_limit * region_area_ratio))
        count_for_region = min(count_for_region, remaining, region_count)
        remaining -= count_for_region
        region_placements, _packed_count = _pack_rectangles_in_polygon(
            region,
            rect_length_m=panel_length_m,
            rect_width_m=panel_width_m,
            max_rectangles=count_for_region,
            row_gap_m=max(0.2, panel_width_m * 0.15),
            col_gap_m=max(0.1, panel_length_m * 0.08),
        )
        placements_by_region.append(region_placements)

    if remaining > 0:
        for region_index, region in enumerate(valid_region_polygons):
            if remaining <= 0:
                break
            already_sampled = len(placements_by_region[region_index])
            region_count = counts_by_region[region_index]
            extra_needed = min(remaining, max(0, region_count - already_sampled))
            if extra_needed <= 0:
                continue
            region_placements, _packed_count = _pack_rectangles_in_polygon(
                region,
                rect_length_m=panel_length_m,
                rect_width_m=panel_width_m,
                max_rectangles=already_sampled + extra_needed,
                row_gap_m=max(0.2, panel_width_m * 0.15),
                col_gap_m=max(0.1, panel_length_m * 0.08),
            )
            placements_by_region[region_index] = region_placements
            remaining -= extra_needed

    placements = [placement for region in placements_by_region for placement in region]
    return placements, len(placements), total_count


def _spacing_box_dimensions(area_m2: float) -> tuple[float, float]:
    width = area_m2 ** 0.5
    length = width
    return length, width


def _subcell_bbox(cell_bbox: BoundingBox, row: int, col: int, grid_size: int) -> BoundingBox:
    lat_span = cell_bbox.max_lat - cell_bbox.min_lat
    lon_span = cell_bbox.max_lon - cell_bbox.min_lon
    min_lat = cell_bbox.min_lat + (lat_span * row / grid_size)
    max_lat = cell_bbox.min_lat + (lat_span * (row + 1) / grid_size)
    min_lon = cell_bbox.min_lon + (lon_span * col / grid_size)
    max_lon = cell_bbox.min_lon + (lon_span * (col + 1) / grid_size)
    return BoundingBox(
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
    )


def _subcell_polygon(sub_bbox: BoundingBox) -> list[Coordinate]:
    return [
        Coordinate(lat=sub_bbox.min_lat, lon=sub_bbox.min_lon),
        Coordinate(lat=sub_bbox.min_lat, lon=sub_bbox.max_lon),
        Coordinate(lat=sub_bbox.max_lat, lon=sub_bbox.max_lon),
        Coordinate(lat=sub_bbox.max_lat, lon=sub_bbox.min_lon),
    ]


def _merge_valid_subcells(
    cell: dict,
    valid_mask: list[list[bool]],
    grid_size: int,
) -> tuple[list[list[Coordinate]], list[float]]:
    polygons: list[list[Coordinate]] = []
    areas: list[float] = []
    subcell_area_m2 = cell["area_m2"] / (grid_size * grid_size)
    active_runs: dict[tuple[int, int], tuple[int, int]] = {}

    for row in range(grid_size):
        row_runs: list[tuple[int, int]] = []
        col = 0
        while col < grid_size:
            if not valid_mask[row][col]:
                col += 1
                continue
            start_col = col
            while col + 1 < grid_size and valid_mask[row][col + 1]:
                col += 1
            row_runs.append((start_col, col))
            col += 1

        next_active_runs: dict[tuple[int, int], tuple[int, int]] = {}
        for run in row_runs:
            if run in active_runs:
                next_active_runs[run] = (active_runs[run][0], row)
            else:
                next_active_runs[run] = (row, row)

        for run, (start_row, end_row) in active_runs.items():
            if run in next_active_runs:
                continue
            start_col, end_col = run
            run_bbox = BoundingBox(
                min_lat=cell["bbox"].min_lat
                + (cell["bbox"].max_lat - cell["bbox"].min_lat) * start_row / grid_size,
                min_lon=cell["bbox"].min_lon
                + (cell["bbox"].max_lon - cell["bbox"].min_lon) * start_col / grid_size,
                max_lat=cell["bbox"].min_lat
                + (cell["bbox"].max_lat - cell["bbox"].min_lat) * (end_row + 1) / grid_size,
                max_lon=cell["bbox"].min_lon
                + (cell["bbox"].max_lon - cell["bbox"].min_lon) * (end_col + 1) / grid_size,
            )
            polygons.append(_subcell_polygon(run_bbox))
            areas.append((end_row - start_row + 1) * (end_col - start_col + 1) * subcell_area_m2)

        active_runs = next_active_runs

    for run, (start_row, end_row) in active_runs.items():
        start_col, end_col = run
        run_bbox = BoundingBox(
            min_lat=cell["bbox"].min_lat
            + (cell["bbox"].max_lat - cell["bbox"].min_lat) * start_row / grid_size,
            min_lon=cell["bbox"].min_lon
            + (cell["bbox"].max_lon - cell["bbox"].min_lon) * start_col / grid_size,
            max_lat=cell["bbox"].min_lat
            + (cell["bbox"].max_lat - cell["bbox"].min_lat) * (end_row + 1) / grid_size,
            max_lon=cell["bbox"].min_lon
            + (cell["bbox"].max_lon - cell["bbox"].min_lon) * (end_col + 1) / grid_size,
        )
        polygons.append(_subcell_polygon(run_bbox))
        areas.append((end_row - start_row + 1) * (end_col - start_col + 1) * subcell_area_m2)

    return polygons, areas


def _build_solar_validity_mask(
    cell: dict,
    imagery: ImageryRaster | None,
    buildings: list[BuildingFootprint],
    roads: list[RoadFeature],
    grid_size: int = 8,
) -> tuple[list[list[Coordinate]], list[float], float]:
    subcell_area_m2 = cell["area_m2"] / (grid_size * grid_size)
    has_live_buildings = bool(buildings)
    has_live_roads = bool(roads)
    sparse_live_roads = len(roads) <= 5
    base_min_road_distance_m = (
        12.0 if has_live_roads and sparse_live_roads else (30.0 if has_live_roads else 0.0)
    )

    def build_mask(
        *,
        max_built_ratio: float,
        min_road_distance_m: float,
        max_water_ratio: float,
        max_shadow_ratio: float,
        max_impervious_ratio: float,
        max_slope_deg: float,
    ) -> tuple[list[list[bool]], float]:
        valid_mask = [[False for _ in range(grid_size)] for _ in range(grid_size)]
        usable_area_m2 = 0.0
        for row in range(grid_size):
            for col in range(grid_size):
                sub_bbox = _subcell_bbox(cell["bbox"], row, col, grid_size)
                center = Coordinate(
                    lat=(sub_bbox.min_lat + sub_bbox.max_lat) / 2.0,
                    lon=(sub_bbox.min_lon + sub_bbox.max_lon) / 2.0,
                )
                feature_seed = {
                    "center_lat": center.lat,
                    "center_lon": center.lon,
                }
                landcover = (
                    sample_imagery_features(imagery, sub_bbox) if imagery else None
                ) or proxy_landcover(feature_seed)
                building_area_m2 = sum(
                    overlap_building_area_m2(sub_bbox, building) for building in buildings
                )
                built_ratio = clamp(building_area_m2 / max(subcell_area_m2, 1.0), 0.0, 1.0)
                road_distance_m = (
                    nearest_road_distance_m(center, roads) if roads else 9999.0
                )
                water_ratio = clamp(landcover.get("water_ratio", 0.0), 0.0, 1.0)
                water_ratio = max(water_ratio, cell.get("vector_water_ratio", 0.0))
                shadow_ratio = clamp(landcover.get("shadow_ratio", 0.0), 0.0, 1.0)
                impervious_ratio = clamp(landcover.get("impervious_ratio", 0.0), 0.0, 1.0)

                is_valid = (
                    built_ratio < max_built_ratio
                    and road_distance_m >= min_road_distance_m
                    and water_ratio < max_water_ratio
                    and shadow_ratio < max_shadow_ratio
                    and impervious_ratio < max_impervious_ratio
                    and cell["slope_deg"] < max_slope_deg
                )
                valid_mask[row][col] = is_valid
                if is_valid:
                    usable_area_m2 += subcell_area_m2
        return valid_mask, usable_area_m2

    valid_mask, usable_area_m2 = build_mask(
        max_built_ratio=0.72 if has_live_buildings else 0.16,
        min_road_distance_m=base_min_road_distance_m,
        max_water_ratio=0.08,
        max_shadow_ratio=0.55 if has_live_buildings else 0.68,
        max_impervious_ratio=0.92 if has_live_buildings else 0.9,
        max_slope_deg=9.5,
    )

    if not has_live_buildings and not has_live_roads and usable_area_m2 < max(600.0, cell["area_m2"] * 0.1):
        valid_mask, usable_area_m2 = build_mask(
            max_built_ratio=0.28,
            min_road_distance_m=0.0,
            max_water_ratio=0.12,
            max_shadow_ratio=0.82,
            max_impervious_ratio=0.98,
            max_slope_deg=11.0,
        )

    valid_region_polygons, valid_region_areas_m2 = _merge_valid_subcells(
        cell,
        valid_mask,
        grid_size,
    )
    return valid_region_polygons, valid_region_areas_m2, usable_area_m2


def _building_footprints_in_cell(
    cell_bbox: BoundingBox,
    buildings: list[BuildingFootprint],
    minimum_area_m2: float = 20.0,
) -> tuple[list[list[Coordinate]], list[float], float]:
    polygons: list[list[Coordinate]] = []
    areas: list[float] = []
    total_area_m2 = 0.0

    for building in buildings:
        clipped = clip_polygon_to_bbox(building.polygon, cell_bbox)
        if len(clipped) < 4:
            continue
        try:
            area_m2, _ = polygon_area_and_centroid(clipped)
        except ValueError:
            continue
        if area_m2 < minimum_area_m2:
            continue
        polygons.append(clipped[:-1] if clipped[0] == clipped[-1] else clipped)
        areas.append(area_m2)
        total_area_m2 += area_m2

    return polygons, areas, total_area_m2


def _build_open_land_validity_mask(
    *,
    cell: dict,
    imagery: ImageryRaster | None,
    buildings: list[BuildingFootprint],
    roads: list[RoadFeature],
    max_built_ratio: float,
    min_road_distance_m: float,
    max_water_ratio: float,
    max_shadow_ratio: float,
    max_vegetation_ratio: float,
    max_impervious_ratio: float,
    max_slope_deg: float,
    grid_size: int = 8,
) -> tuple[list[list[Coordinate]], list[float], float]:
    subcell_area_m2 = cell["area_m2"] / (grid_size * grid_size)
    subcell_side_m = subcell_area_m2 ** 0.5
    subcell_half_diagonal_m = subcell_side_m / (2 ** 0.5)
    valid_mask = [[False for _ in range(grid_size)] for _ in range(grid_size)]
    usable_area_m2 = 0.0

    for row in range(grid_size):
        for col in range(grid_size):
            sub_bbox = _subcell_bbox(cell["bbox"], row, col, grid_size)
            center = Coordinate(
                lat=(sub_bbox.min_lat + sub_bbox.max_lat) / 2.0,
                lon=(sub_bbox.min_lon + sub_bbox.max_lon) / 2.0,
            )
            feature_seed = {"center_lat": center.lat, "center_lon": center.lon}
            landcover = (
                sample_imagery_features(imagery, sub_bbox) if imagery else None
            ) or proxy_landcover(feature_seed)

            building_area_m2 = sum(
                overlap_building_area_m2(sub_bbox, building) for building in buildings
            )
            built_ratio = clamp(building_area_m2 / max(subcell_area_m2, 1.0), 0.0, 1.0)
            road_distance_m = (
                nearest_road_distance_m(center, roads) if roads else 9_999.0
            )
            required_road_clearance_m = min_road_distance_m + subcell_half_diagonal_m
            water_ratio = clamp(landcover.get("water_ratio", 0.0), 0.0, 1.0)
            water_ratio = max(
                water_ratio,
                clamp(
                    sum(overlap_water_area_m2(sub_bbox, water) for water in cell.get("water_features", []))
                    / max(subcell_area_m2, 1.0),
                    0.0,
                    1.0,
                ),
            )
            shadow_ratio = clamp(landcover.get("shadow_ratio", 0.0), 0.0, 1.0)
            vegetation_ratio = clamp(landcover.get("vegetation_ratio", 0.0), 0.0, 1.0)
            impervious_ratio = clamp(landcover.get("impervious_ratio", 0.0), 0.0, 1.0)

            is_valid = (
                built_ratio <= max_built_ratio
                and road_distance_m >= required_road_clearance_m
                and water_ratio <= max_water_ratio
                and shadow_ratio <= max_shadow_ratio
                and vegetation_ratio <= max_vegetation_ratio
                and impervious_ratio <= max_impervious_ratio
                and cell["slope_deg"] <= max_slope_deg
            )
            valid_mask[row][col] = is_valid
            if is_valid:
                usable_area_m2 += subcell_area_m2

    polygons, areas = _merge_valid_subcells(cell, valid_mask, grid_size)
    return polygons, areas, usable_area_m2


def enrich_cells(
    cells: list[dict],
    segmentation_features: dict[str, dict[str, float]],
    segmentation_source: str,
    imagery_source: str,
    buildings: list[BuildingFootprint],
    roads: list[RoadFeature],
    waters: list[WaterFeature],
    vector_source: str,
    slopes_by_cell: dict[str, float],
    terrain_source: str,
) -> None:
    for cell in cells:
        cell_bbox = cell["bbox"]
        landcover = segmentation_features[cell["id"]]

        if buildings:
            building_area_m2 = sum(
                overlap_building_area_m2(cell_bbox, building)
                for building in buildings
            )
        else:
            building_area_m2 = (
                cell["area_m2"]
                * (0.08 + 0.55 * pseudo(cell["center_lat"], cell["center_lon"], "built"))
                * 0.55
            )

        remote_building_ratio = landcover.get("building_ratio")
        if remote_building_ratio is not None:
            building_area_m2 = max(
                building_area_m2,
                clamp(remote_building_ratio, 0.0, 1.0) * cell["area_m2"],
            )

        built_ratio = clamp(building_area_m2 / cell["area_m2"], 0.0, 1.0)
        if not buildings:
            built_ratio = max(built_ratio, landcover["impervious_ratio"] * 0.7)
            building_area_m2 = built_ratio * cell["area_m2"]

        road_distance_m = (
            nearest_road_distance_m(
                Coordinate(lat=cell["center_lat"], lon=cell["center_lon"]),
                roads,
            )
            if roads
            else 150 + 2_000 * pseudo(cell["center_lat"], cell["center_lon"], "road")
        )

        vegetation_ratio = clamp(landcover["vegetation_ratio"], 0.0, 1.0)
        water_ratio = clamp(landcover["water_ratio"], 0.0, 0.95)
        water_area_m2 = (
            sum(overlap_water_area_m2(cell_bbox, water) for water in waters)
            if waters
            else 0.0
        )
        vector_water_ratio = clamp(water_area_m2 / max(cell["area_m2"], 1.0), 0.0, 1.0)
        water_ratio = max(water_ratio, vector_water_ratio)
        shading_factor = clamp(
            max(landcover["shadow_ratio"], vegetation_ratio * 0.35),
            0.0,
            1.0,
        )
        slope_deg = slopes_by_cell.get(cell["id"], 0.2)

        rooftop_area_m2 = building_area_m2 * 0.88
        open_land_ratio = clamp(
            1.0 - built_ratio - water_ratio - vegetation_ratio * 0.55,
            0.0,
            1.0,
        )
        open_land_area_m2 = cell["area_m2"] * open_land_ratio
        unobstructed_ratio = clamp(
            1.0 - built_ratio * 0.85 - vegetation_ratio * 0.45 - water_ratio * 0.9,
            0.0,
            1.0,
        )

        cell.update(
            {
                "building_area_m2": building_area_m2,
                "rooftop_area_m2": rooftop_area_m2,
                "open_land_area_m2": open_land_area_m2,
                "slope_deg": slope_deg,
                "shading_factor": shading_factor,
                "road_distance_m": road_distance_m,
                "unobstructed_ratio": unobstructed_ratio,
                "water_area_m2": water_area_m2,
                "vector_water_ratio": vector_water_ratio,
                "vegetation_ratio": vegetation_ratio,
                "water_ratio": water_ratio,
                "built_ratio": built_ratio,
                "impervious_ratio": landcover["impervious_ratio"],
                "imagery_used": imagery_source != "not-requested" and "fallback" not in imagery_source,
                "vector_data_used": bool(buildings or roads),
                "segmentation_source": segmentation_source,
                "imagery_source": imagery_source,
                "vector_source": vector_source,
                "terrain_source": terrain_source,
                "water_features": waters,
            }
        )


def solar_candidate(
    cell: dict,
    idx: int,
    solar_spec: SolarAssetSpec | None = None,
    imagery: ImageryRaster | None = None,
    buildings: list[BuildingFootprint] | None = None,
    roads: list[RoadFeature] | None = None,
) -> CandidateRegion | None:
    if solar_spec is None:
        solar_spec = SolarAssetSpec()
    if buildings is None:
        buildings = []
    if roads is None:
        roads = []
    if "bbox" not in cell and "polygon" in cell:
        cell = dict(cell)
        cell["bbox"] = BoundingBox(
            min_lat=min(point.lat for point in cell["polygon"]),
            min_lon=min(point.lon for point in cell["polygon"]),
            max_lat=max(point.lat for point in cell["polygon"]),
            max_lon=max(point.lon for point in cell["polygon"]),
        )
    candidate, _reason = evaluate_solar_candidate(
        cell,
        idx,
        solar_spec,
        imagery,
        buildings,
        roads,
    )
    return candidate


def evaluate_solar_candidate(
    cell: dict,
    idx: int,
    solar_spec: SolarAssetSpec,
    imagery: ImageryRaster | None,
    buildings: list[BuildingFootprint],
    roads: list[RoadFeature],
) -> tuple[CandidateRegion | None, str | None]:
    irradiance = solar_irradiance_proxy(cell["center_lat"])
    rooftop_polygons, rooftop_areas_m2, rooftop_area_m2 = _building_footprints_in_cell(
        cell["bbox"],
        buildings,
        minimum_area_m2=24.0,
    )
    rooftop_usable_area_m2 = rooftop_area_m2 * 0.82
    open_land_polygons, open_land_areas_m2, open_land_usable_area_m2 = _build_open_land_validity_mask(
        cell=cell,
        imagery=imagery,
        buildings=buildings,
        roads=roads,
        max_built_ratio=0.08 if buildings else 0.22,
        min_road_distance_m=14.0 if roads else 0.0,
        max_water_ratio=0.06,
        max_shadow_ratio=0.5,
        max_vegetation_ratio=0.72,
        max_impervious_ratio=0.86,
        max_slope_deg=9.5,
        grid_size=12 if (buildings or roads) else 8,
    )

    if rooftop_polygons and rooftop_usable_area_m2 >= 45.0:
        valid_region_polygons = rooftop_polygons
        valid_region_areas_m2 = rooftop_areas_m2
        usable_solar_area = rooftop_usable_area_m2
        validity_source = "rooftop_buildings"
    else:
        valid_region_polygons = open_land_polygons
        valid_region_areas_m2 = open_land_areas_m2
        usable_solar_area = open_land_usable_area_m2
        validity_source = "open_land_mask"

    min_usable_area_m2 = (
        45.0
        if validity_source == "rooftop_buildings"
        else max(600.0, min(2_500.0, cell["area_m2"] * 0.1))
    )
    if usable_solar_area < min_usable_area_m2:
        if cell.get("water_ratio", 0.0) >= 0.5 and not buildings and not roads:
            return None, "low_usable_area"
        if not (buildings or roads):
            fallback_open_area = clamp(
                cell["open_land_area_m2"] * cell.get("unobstructed_ratio", 1.0),
                0.0,
                cell["area_m2"],
            )
            if fallback_open_area >= min_usable_area_m2:
                usable_solar_area = fallback_open_area
                valid_region_polygons = [cell["polygon"]]
                valid_region_areas_m2 = [fallback_open_area]
                validity_source = "open_land_fallback"
            else:
                return None, "low_usable_area"
        else:
            return None, "low_usable_area"

    estimate = analyze_solar_project(
        SolarProjectInputs(
            area_m2=usable_solar_area,
            centroid_lat=cell["center_lat"],
            centroid_lon=cell["center_lon"],
            panel_area_m2=solar_spec.panel_area_m2,
            panel_rating_w=solar_spec.panel_rating_w,
            panel_cost_usd=solar_spec.panel_cost_usd,
            construction_cost_per_m2_usd=solar_spec.construction_cost_per_m2_usd,
            packing_efficiency=solar_spec.packing_efficiency,
            performance_ratio=solar_spec.performance_ratio,
            sunlight_threshold_kwh_m2_yr=solar_spec.sunlight_threshold_kwh_m2_yr,
            panel_tilt_deg=DEFAULT_PANEL_TILT_DEG,
            panel_azimuth_deg=DEFAULT_PANEL_AZIMUTH_DEG,
            state=None,
        ),
        sunlight_intensity_kwh_m2_yr=irradiance,
        weather_source="irradiance-proxy",
        low_sunlight_reason="Cell-level solar resource falls below the recommended threshold.",
        low_capacity_reason="The usable subregion is too small to host a meaningful packed solar layout.",
        success_reason="The subregion has enough usable area and solar resource for a practical packed layout.",
    )

    minimum_panel_count = 8 if validity_source == "rooftop_buildings" else 24
    if estimate.layout.panel_count < minimum_panel_count:
        return None, "low_panel_count"

    flatness_score = clamp((8.0 - cell["slope_deg"]) / 8.0, 0.0, 1.0)
    shade_score = clamp(1.0 - cell["shading_factor"], 0.0, 1.0)
    rooftop_area_m2 = cell.get("building_area_m2", cell.get("rooftop_area_m2", 0.0))
    rooftop_coverage_score = clamp(rooftop_area_m2 / max(cell["area_m2"], 1.0), 0.0, 1.0)
    buildability_score = round(
        100
        * (
            0.40 * shade_score
            + 0.20 * flatness_score
            + 0.15 * clamp(usable_solar_area / 12_000.0, 0.0, 1.0)
            + 0.10 * clamp(1.0 - cell["water_ratio"], 0.0, 1.0)
            + 0.15 * rooftop_coverage_score
        ),
        1,
    )
    score = round(0.45 * estimate.suitability_score + 0.55 * buildability_score, 1)
    if score < 48:
        return None, "low_score"

    _valid_region_polygons, packing_block_polygons = _build_visual_solar_layout(
        valid_region_polygons=valid_region_polygons,
        valid_region_areas_m2=valid_region_areas_m2,
        packed_usable_area_m2=estimate.layout.usable_area_m2,
    )
    (
        placement_polygons,
        display_panel_count,
        packed_panel_count,
    ) = _build_solar_panel_placements(
        valid_region_polygons=valid_region_polygons,
        valid_region_areas_m2=valid_region_areas_m2,
        panel_area_m2=solar_spec.panel_area_m2,
    )
    effective_panel_count = (
        packed_panel_count
        if validity_source == "rooftop_buildings"
        else min(estimate.layout.panel_count, packed_panel_count)
    )
    minimum_panel_count = 8 if validity_source == "rooftop_buildings" else 24
    if effective_panel_count < minimum_panel_count:
        return None, "low_panel_count"

    packed_usable_area_m2 = effective_panel_count * solar_spec.panel_area_m2
    installed_capacity_kw = round(
        (effective_panel_count * solar_spec.panel_rating_w) / 1000.0,
        2,
    )
    output_scale = packed_usable_area_m2 / max(estimate.layout.usable_area_m2, 1.0)
    estimated_annual_output_kwh = round(
        estimate.estimated_annual_output_kwh * output_scale,
        2,
    )
    estimated_installation_cost_usd = round(
        effective_panel_count * solar_spec.panel_cost_usd
        + packed_usable_area_m2 * solar_spec.construction_cost_per_m2_usd,
        2,
    )
    panel_length_m, panel_width_m = _estimate_panel_dimensions_from_area(
        solar_spec.panel_area_m2
    )

    return CandidateRegion(
        id=f"solar-{idx}",
        use_type="solar",
        polygon=valid_region_polygons[0] if valid_region_polygons else cell["polygon"],
        area_m2=round(usable_solar_area, 2),
        feasibility_score=score,
        reasoning=[
            (
                "Building footprints define rooftop-ready solar regions in this cell."
                if validity_source == "rooftop_buildings"
                else "Segmented open land and road screening define a usable solar build envelope in this cell."
            ),
            estimate.suitability_reason,
            "Roads, water, slope, and shading stay within a practical range for a packed solar layout.",
        ]
        + (
            ["The usable area comes from the open-land fallback."]
            if validity_source == "open_land_fallback"
            else []
        ),
        estimated_annual_output_kwh=estimated_annual_output_kwh,
        estimated_installation_cost_usd=estimated_installation_cost_usd,
        metadata={
            "model_source": estimate.model_source,
            "weather_source": estimate.weather_source,
            "panel_count": effective_panel_count,
            "installed_capacity_kw": installed_capacity_kw,
            "irradiance_kwh_m2_yr": round(irradiance, 2),
            "usable_solar_area_m2": round(usable_solar_area, 2),
            "packed_usable_area_m2": round(packed_usable_area_m2, 2),
            "valid_region_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in valid_region_polygons
            ],
            "packing_block_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in packing_block_polygons
            ],
            "placement_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in placement_polygons
            ],
            "display_panel_count": display_panel_count,
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "vegetation_ratio": round(cell["vegetation_ratio"], 3),
            "water_ratio": round(cell["water_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
            "validity_source": validity_source,
            "panel_length_m": round(panel_length_m, 3),
            "panel_width_m": round(panel_width_m, 3),
        },
    ), None


def wind_candidate(
    cell: dict,
    idx: int,
    wind_spec: WindAssetSpec | None = None,
    imagery: ImageryRaster | None = None,
    buildings: list[BuildingFootprint] | None = None,
    roads: list[RoadFeature] | None = None,
) -> CandidateRegion | None:
    wind_spec = wind_spec or WindAssetSpec()
    buildings = buildings or []
    roads = roads or []
    valid_region_polygons, valid_region_areas_m2, open_land = _build_open_land_validity_mask(
        cell=cell,
        imagery=imagery,
        buildings=buildings,
        roads=roads,
        max_built_ratio=0.08 if buildings else 0.22,
        min_road_distance_m=20.0,
        max_water_ratio=0.10,
        max_shadow_ratio=0.95,  # shadow irrelevant for turbines
        max_vegetation_ratio=0.90,  # crops/fields are viable turbine land
        max_impervious_ratio=0.85,
        max_slope_deg=8.0,
        grid_size=12 if (buildings or roads) else 8,
    )
    if open_land < 10_000:
        return None

    wind_speed = wind_speed_proxy(cell["center_lat"], cell["center_lon"])
    turbine_count = max(0, int(open_land // wind_spec.spacing_area_m2))
    if turbine_count < 1:
        return None

    cf = clamp(0.35 * (wind_speed / 7.0) ** 2.5, 0.05, 0.6)
    annual_kwh = turbine_count * wind_spec.turbine_rating_kw * 8_760 * cf
    cost = turbine_count * wind_spec.turbine_cost_usd + open_land * 16.0

    land_score = clamp(open_land / 120_000.0, 0.0, 1.0)
    wind_score = clamp((wind_speed - 5.0) / 4.0, 0.0, 1.0)
    obstruction_score = clamp(cell["unobstructed_ratio"], 0.0, 1.0)
    slope_score = clamp((9.0 - cell["slope_deg"]) / 9.0, 0.0, 1.0)
    score = round(
        100
        * (
            0.4 * wind_score
            + 0.25 * land_score
            + 0.2 * obstruction_score
            + 0.15 * slope_score
        ),
        1,
    )
    if score < 45:
        return None

    primary_polygon = (
        valid_region_polygons[
            max(range(len(valid_region_polygons)), key=lambda index: valid_region_areas_m2[index])
        ]
        if valid_region_polygons
        else cell["polygon"]
    )
    turbine_length_m, turbine_width_m = _spacing_box_dimensions(wind_spec.spacing_area_m2)
    placement_polygons = []
    remaining_turbines = turbine_count
    for polygon, area_m2 in zip(valid_region_polygons, valid_region_areas_m2):
        if remaining_turbines <= 0:
            break
        share = clamp(area_m2 / max(open_land, 1.0), 0.0, 1.0)
        count_for_polygon = min(
            remaining_turbines,
            max(1, round(turbine_count * share)),
        )
        packed, packed_count = _pack_rectangles_in_polygon(
            polygon,
            rect_length_m=turbine_length_m,
            rect_width_m=turbine_width_m,
            max_rectangles=count_for_polygon,
            row_gap_m=max(6.0, turbine_width_m * 0.08),
            col_gap_m=max(6.0, turbine_length_m * 0.08),
        )
        placement_polygons.extend(packed)
        remaining_turbines -= packed_count

    if not placement_polygons and valid_region_polygons:
        placement_polygons = _build_box_layout_within_polygons(
            valid_region_polygons,
            valid_region_areas_m2,
            turbine_count,
            wind_spec.spacing_area_m2,
            fill_ratio=0.68,
        )

    return CandidateRegion(
        id=f"wind-{idx}",
        use_type="wind",
        polygon=primary_polygon,
        area_m2=round(open_land, 2),
        feasibility_score=score,
        reasoning=[
            "Screened open land keeps buildings and roads out of the main turbine footprint.",
            "Building and vegetation obstruction remain low enough for wide turbine setbacks.",
            "Wind proxy and live terrain slope remain in a practical turbine deployment range.",
        ],
        estimated_annual_output_kwh=round(annual_kwh, 2),
        estimated_installation_cost_usd=round(cost, 2),
        metadata={
            "turbine_count": turbine_count,
            "wind_speed_100m_mps": round(wind_speed, 2),
            "capacity_factor": round(cf, 3),
            "turbine_rating_kw": round(wind_spec.turbine_rating_kw, 2),
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "vegetation_ratio": round(cell["vegetation_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
            "valid_region_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in valid_region_polygons
            ],
            "placement_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in placement_polygons
            ],
        },
    )


def data_center_candidate(
    cell: dict,
    idx: int,
    data_center_spec: DataCenterAssetSpec | None = None,
    imagery: ImageryRaster | None = None,
    buildings: list[BuildingFootprint] | None = None,
    roads: list[RoadFeature] | None = None,
) -> CandidateRegion | None:
    data_center_spec = data_center_spec or DataCenterAssetSpec()
    buildings = buildings or []
    roads = roads or []
    valid_region_polygons, valid_region_areas_m2, open_land = _build_open_land_validity_mask(
        cell=cell,
        imagery=imagery,
        buildings=buildings,
        roads=roads,
        max_built_ratio=0.06 if buildings else 0.15,
        min_road_distance_m=10.0,
        max_water_ratio=0.04,
        max_shadow_ratio=0.55,
        max_vegetation_ratio=0.72,
        max_impervious_ratio=0.82,
        max_slope_deg=6.0,
        grid_size=12 if (buildings or roads) else 8,
    )
    if open_land < 8_000:
        return None

    flatness_score = clamp((8.0 - cell["slope_deg"]) / 8.0, 0.0, 1.0)
    rooftop_area_m2 = cell.get("building_area_m2", cell.get("rooftop_area_m2", 0.0))
    rooftop_coverage_score = clamp(rooftop_area_m2 / max(cell["area_m2"], 1.0), 0.0, 1.0)
    area_score = clamp(open_land / 60_000.0, 0.0, 1.0)
    access_score = clamp(1.0 - cell["road_distance_m"] / 2200.0, 0.0, 1.0)
    score = round(100 * (0.45 * flatness_score + 0.3 * area_score + 0.15 * access_score + 0.10 * rooftop_coverage_score), 1)
    if score < 52:
        return None
    installed_capacity_kw = open_land * data_center_spec.power_density_kw_per_m2
    it_load_mw = max(0.3, installed_capacity_kw / 1000.0)
    capex = (
        open_land * data_center_spec.construction_cost_per_m2_usd
        + installed_capacity_kw * data_center_spec.fit_out_cost_per_kw_usd
    )
    primary_polygon = (
        valid_region_polygons[
            max(range(len(valid_region_polygons)), key=lambda index: valid_region_areas_m2[index])
        ]
        if valid_region_polygons
        else cell["polygon"]
    )

    return CandidateRegion(
        id=f"dc-{idx}",
        use_type="data_center",
        polygon=primary_polygon,
        area_m2=round(open_land, 2),
        feasibility_score=score,
        reasoning=[
            "The screened open-land polygons remove buildings and road corridors from the main campus footprint.",
            "Road vectors show workable logistics access for construction and operations.",
            "Live terrain slope indicates a practical build envelope for support infrastructure.",
        ],
        estimated_annual_output_kwh=None,
        estimated_installation_cost_usd=round(capex, 2),
        metadata={
            "estimated_it_load_mw": round(it_load_mw, 2),
            "installed_capacity_kw": round(installed_capacity_kw, 2),
            "road_distance_m": round(cell["road_distance_m"], 1),
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "water_ratio": round(cell["water_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
            "valid_region_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in valid_region_polygons
            ],
            "placement_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in ([primary_polygon] if valid_region_polygons else [cell["polygon"]])
            ],
        },
    )
