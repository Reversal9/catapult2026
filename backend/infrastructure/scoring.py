from __future__ import annotations

from schemas import (
    BoundingBox,
    CandidateRegion,
    Coordinate,
    DEFAULT_PANEL_AZIMUTH_DEG,
    DEFAULT_PANEL_TILT_DEG,
    SolarAssetSpec,
)
from solar_project import SolarProjectInputs, analyze_solar_project

from .common import clamp, pseudo, solar_irradiance_proxy, wind_speed_proxy
from .grid import nearest_road_distance_m, overlap_building_area_m2
from .models import BuildingFootprint, ImageryRaster, RoadFeature
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
        max_built_ratio=0.04 if has_live_buildings else 0.16,
        min_road_distance_m=base_min_road_distance_m,
        max_water_ratio=0.08,
        max_shadow_ratio=0.35 if has_live_buildings else 0.68,
        max_impervious_ratio=0.58 if has_live_buildings else 0.9,
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


def enrich_cells(
    cells: list[dict],
    segmentation_features: dict[str, dict[str, float]],
    segmentation_source: str,
    imagery_source: str,
    buildings: list[BuildingFootprint],
    roads: list[RoadFeature],
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
            }
        )


def solar_candidate(
    cell: dict,
    idx: int,
    solar_spec: SolarAssetSpec,
    imagery: ImageryRaster | None,
    buildings: list[BuildingFootprint],
    roads: list[RoadFeature],
) -> CandidateRegion | None:
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
    valid_region_polygons, valid_region_areas_m2, usable_solar_area = _build_solar_validity_mask(
        cell=cell,
        imagery=imagery,
        buildings=buildings,
        roads=roads,
    )
    min_usable_area_m2 = max(600.0, min(2_500.0, cell["area_m2"] * 0.1))
    validity_source = "mask"
    if usable_solar_area < min_usable_area_m2:
        fallback_open_area = clamp(
            cell["open_land_area_m2"] * cell.get("unobstructed_ratio", 1.0),
            0.0,
            cell["area_m2"],
        )
        if fallback_open_area >= min_usable_area_m2:
            usable_solar_area = fallback_open_area
            valid_region_polygons = [cell["polygon"]]
            valid_region_areas_m2 = [usable_solar_area]
            validity_source = "open_land_fallback"
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

    if estimate.layout.panel_count < 24:
        return None, "low_panel_count"

    flatness_score = clamp((8.0 - cell["slope_deg"]) / 8.0, 0.0, 1.0)
    shade_score = clamp(1.0 - cell["shading_factor"], 0.0, 1.0)
    buildability_score = round(
        100
        * (
            0.45 * shade_score
            + 0.25 * flatness_score
            + 0.15 * clamp(usable_solar_area / 12_000.0, 0.0, 1.0)
            + 0.15 * clamp(1.0 - cell["water_ratio"] - cell["built_ratio"] * 0.35, 0.0, 1.0)
        ),
        1,
    )
    score = round(
        0.45 * estimate.suitability_score + 0.55 * buildability_score,
        1,
    )
    if score < 48:
        return None, "low_score"

    _valid_region_polygons, packing_block_polygons = _build_visual_solar_layout(
        valid_region_polygons=valid_region_polygons,
        valid_region_areas_m2=valid_region_areas_m2,
        packed_usable_area_m2=estimate.layout.usable_area_m2,
    )

    return CandidateRegion(
        id=f"solar-{idx}",
        use_type="solar",
        polygon=valid_region_polygons[0] if valid_region_polygons else cell["polygon"],
        area_m2=round(usable_solar_area, 2),
        feasibility_score=score,
    reasoning=[
        "Building footprints and segmented open land define a usable solar build envelope in this cell.",
        estimate.suitability_reason,
        "Slope, vegetation, and shading remain in a practical range for a packed solar layout.",
    ] + (
        ["The usable area comes from the open-land fallback."]
        if validity_source == "open_land_fallback"
        else []
    ),
        estimated_annual_output_kwh=round(estimate.estimated_annual_output_kwh, 2),
        estimated_installation_cost_usd=round(estimate.cost.total_project_cost_usd, 2),
        metadata={
            "model_source": estimate.model_source,
            "weather_source": estimate.weather_source,
            "panel_count": estimate.layout.panel_count,
            "installed_capacity_kw": round(estimate.layout.installed_capacity_kw, 2),
            "irradiance_kwh_m2_yr": round(irradiance, 2),
            "usable_solar_area_m2": round(usable_solar_area, 2),
            "packed_usable_area_m2": round(estimate.layout.usable_area_m2, 2),
            "valid_region_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in valid_region_polygons
            ],
            "packing_block_polygons": [
                [point.model_dump() for point in polygon]
                for polygon in packing_block_polygons
            ],
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "vegetation_ratio": round(cell["vegetation_ratio"], 3),
            "water_ratio": round(cell["water_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
            "validity_source": validity_source,
        },
    ), None


def wind_candidate(cell: dict, idx: int) -> CandidateRegion | None:
    open_land = cell["open_land_area_m2"] * cell["unobstructed_ratio"]
    if open_land < 18_000:
        return None

    wind_speed = wind_speed_proxy(cell["center_lat"], cell["center_lon"])
    turbine_count = max(0, int(open_land // 45_000))
    if turbine_count < 1:
        return None

    cf = clamp(0.35 * (wind_speed / 7.0) ** 2.5, 0.05, 0.6)
    annual_kwh = turbine_count * 2_000 * 8_760 * cf
    cost = turbine_count * 1_850_000 + open_land * 16.0

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
    if score < 58:
        return None

    return CandidateRegion(
        id=f"wind-{idx}",
        use_type="wind",
        polygon=cell["polygon"],
        area_m2=round(open_land, 2),
        feasibility_score=score,
        reasoning=[
            "Segmented open land preserves enough spacing for turbine placement.",
            "Building and vegetation obstruction remain low enough for wide turbine setbacks.",
            "Wind proxy and live terrain slope remain in a practical turbine deployment range.",
        ],
        estimated_annual_output_kwh=round(annual_kwh, 2),
        estimated_installation_cost_usd=round(cost, 2),
        metadata={
            "turbine_count": turbine_count,
            "wind_speed_100m_mps": round(wind_speed, 2),
            "capacity_factor": round(cf, 3),
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "vegetation_ratio": round(cell["vegetation_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
        },
    )


def data_center_candidate(cell: dict, idx: int) -> CandidateRegion | None:
    open_land = cell["open_land_area_m2"]
    if open_land < 8_000:
        return None

    flatness_score = clamp((5.5 - cell["slope_deg"]) / 5.5, 0.0, 1.0)
    access_score = clamp(1.0 - cell["road_distance_m"] / 2200.0, 0.0, 1.0)
    area_score = clamp(open_land / 60_000.0, 0.0, 1.0)
    score = round(100 * (0.5 * flatness_score + 0.3 * area_score + 0.2 * access_score), 1)
    if score < 52:
        return None

    it_load_mw = max(0.3, open_land / 18_000.0)
    capex = open_land * 280.0 + it_load_mw * 4_500_000

    return CandidateRegion(
        id=f"dc-{idx}",
        use_type="data_center",
        polygon=cell["polygon"],
        area_m2=round(open_land, 2),
        feasibility_score=score,
        reasoning=[
            "The cell preserves enough contiguous land for a staged campus footprint.",
            "Road vectors show workable logistics access for construction and operations.",
            "Live terrain slope indicates a practical build envelope for support infrastructure.",
        ],
        estimated_annual_output_kwh=None,
        estimated_installation_cost_usd=round(capex, 2),
        metadata={
            "estimated_it_load_mw": round(it_load_mw, 2),
            "road_distance_m": round(cell["road_distance_m"], 1),
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "water_ratio": round(cell["water_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
        },
    )
