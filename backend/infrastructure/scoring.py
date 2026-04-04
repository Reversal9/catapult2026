from __future__ import annotations

from schemas import CandidateRegion, Coordinate

from .common import clamp, pseudo, solar_irradiance_proxy, wind_speed_proxy
from .grid import nearest_road_distance_m, overlap_building_area_m2
from .models import BuildingFootprint, RoadFeature


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


def solar_candidate(cell: dict, idx: int) -> CandidateRegion | None:
    irradiance = solar_irradiance_proxy(cell["center_lat"])
    usable_ground_area = cell["open_land_area_m2"] * clamp(1.0 - cell["water_ratio"], 0.0, 1.0)
    usable_solar_area = cell["rooftop_area_m2"] + 0.5 * usable_ground_area
    if usable_solar_area < 2_500:
        return None

    panel_area = 2.0
    panel_rating_w = 420.0
    panel_count = int(usable_solar_area * 0.72 // panel_area)
    if panel_count < 24:
        return None

    installed_kw = panel_count * panel_rating_w / 1000.0
    annual_kwh = irradiance * usable_solar_area * (panel_rating_w / (1000 * panel_area)) * 0.8
    cost = panel_count * 260.0 + usable_solar_area * 120.0

    flatness_score = clamp((8.0 - cell["slope_deg"]) / 8.0, 0.0, 1.0)
    shade_score = clamp(1.0 - cell["shading_factor"], 0.0, 1.0)
    area_score = clamp(usable_solar_area / 12_000.0, 0.0, 1.0)
    irradiance_score = clamp((irradiance - 1_150.0) / 900.0, 0.0, 1.0)
    score = round(
        100
        * (
            0.35 * area_score
            + 0.3 * irradiance_score
            + 0.2 * shade_score
            + 0.15 * flatness_score
        ),
        1,
    )
    if score < 55:
        return None

    return CandidateRegion(
        id=f"solar-{idx}",
        use_type="solar",
        polygon=cell["polygon"],
        area_m2=round(usable_solar_area, 2),
        feasibility_score=score,
        reasoning=[
            "Building footprints and segmented open land indicate usable solar area in this cell.",
            "Imagery-derived vegetation, water, and shading constraints remain manageable.",
            "Slope and irradiance remain in a practical build range for solar deployment.",
        ],
        estimated_annual_output_kwh=round(annual_kwh, 2),
        estimated_installation_cost_usd=round(cost, 2),
        metadata={
            "panel_count": panel_count,
            "installed_capacity_kw": round(installed_kw, 2),
            "irradiance_kwh_m2_yr": round(irradiance, 2),
            "building_coverage_ratio": round(cell["built_ratio"], 3),
            "vegetation_ratio": round(cell["vegetation_ratio"], 3),
            "water_ratio": round(cell["water_ratio"], 3),
            "slope_deg": round(cell["slope_deg"], 2),
        },
    )


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
