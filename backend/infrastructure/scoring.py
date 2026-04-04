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
from .models import BuildingFootprint, RoadFeature


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
    cell: dict,
    usable_ground_area_m2: float,
    usable_solar_area_m2: float,
    packed_usable_area_m2: float,
) -> tuple[list[list[Coordinate]], list[list[Coordinate]]]:
    cell_area_m2 = max(cell["area_m2"], 1.0)
    rooftop_ratio = clamp(cell["rooftop_area_m2"] / cell_area_m2, 0.0, 0.35)
    ground_ratio = clamp((0.5 * usable_ground_area_m2) / cell_area_m2, 0.0, 0.85)

    valid_regions: list[list[Coordinate]] = []

    if rooftop_ratio > 0.02:
        rooftop_height = 0.16
        rooftop_width = clamp(rooftop_ratio / rooftop_height, 0.18, 0.88)
        valid_regions.append(
            _rect_polygon(
                cell["bbox"],
                0.06,
                0.78,
                0.06 + rooftop_width,
                0.78 + rooftop_height,
            )
        )

    if ground_ratio > 0.03:
        ground_height = clamp(0.36 + ground_ratio * 0.25, 0.32, 0.74)
        ground_width = clamp(ground_ratio / max(ground_height, 0.2), 0.18, 0.88)
        valid_regions.append(
            _rect_polygon(
                cell["bbox"],
                0.08,
                0.08,
                0.08 + ground_width,
                0.08 + ground_height,
            )
        )

    if not valid_regions and usable_solar_area_m2 > 0:
        ratio = clamp(usable_solar_area_m2 / cell_area_m2, 0.05, 0.85)
        side = clamp(ratio**0.5, 0.24, 0.9)
        margin_x = (1.0 - side) / 2.0
        margin_y = (1.0 - side) / 2.0
        valid_regions.append(
            _rect_polygon(
                cell["bbox"],
                margin_x,
                margin_y,
                margin_x + side,
                margin_y + side,
            )
        )

    packing_blocks: list[list[Coordinate]] = []
    packed_ratio = clamp(
        packed_usable_area_m2 / max(usable_solar_area_m2, 1.0),
        0.0,
        1.0,
    )
    for region_index, region in enumerate(valid_regions):
        region_bbox = BoundingBox(
            min_lat=min(point.lat for point in region),
            min_lon=min(point.lon for point in region),
            max_lat=max(point.lat for point in region),
            max_lon=max(point.lon for point in region),
        )
        cols = 3 if region_index == 0 else 2
        rows = 2
        block_margin_x = 0.08
        block_margin_y = 0.12
        usable_width = 1.0 - (block_margin_x * 2)
        usable_height = max(0.2, packed_ratio * 0.72)
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

    return valid_regions, packing_blocks


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
) -> CandidateRegion | None:
    candidate, _reason = evaluate_solar_candidate(cell, idx, solar_spec)
    return candidate


def evaluate_solar_candidate(
    cell: dict,
    idx: int,
    solar_spec: SolarAssetSpec,
) -> tuple[CandidateRegion | None, str | None]:
    irradiance = solar_irradiance_proxy(cell["center_lat"])
    usable_ground_area = cell["open_land_area_m2"] * clamp(1.0 - cell["water_ratio"], 0.0, 1.0)
    usable_solar_area = cell["rooftop_area_m2"] + 0.5 * usable_ground_area
    if usable_solar_area < 2_500:
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

    valid_region_polygons, packing_block_polygons = _build_visual_solar_layout(
        cell=cell,
        usable_ground_area_m2=usable_ground_area,
        usable_solar_area_m2=usable_solar_area,
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
        ],
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
