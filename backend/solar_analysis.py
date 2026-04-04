from __future__ import annotations

from geometry import polygon_area_and_centroid
from schemas import Coordinate, SolarAnalysisRequest, SolarAnalysisResponse
from solar_project import SolarProjectInputs, analyze_solar_project, log_debug


def analyze_solar_polygon(request: SolarAnalysisRequest) -> SolarAnalysisResponse:
    area_m2, centroid = polygon_area_and_centroid(request.points)
    area_km2 = area_m2 / 1_000_000.0
    estimate = analyze_solar_project(
        SolarProjectInputs(
            area_m2=area_m2,
            centroid_lat=centroid.lat,
            centroid_lon=centroid.lon,
            panel_area_m2=request.panel_area_m2,
            panel_rating_w=request.panel_rating_w,
            panel_cost_usd=request.panel_cost_usd,
            construction_cost_per_m2_usd=request.construction_cost_per_m2_usd,
            packing_efficiency=request.packing_efficiency,
            performance_ratio=request.performance_ratio,
            sunlight_threshold_kwh_m2_yr=request.sunlight_threshold_kwh_m2_yr,
            panel_tilt_deg=request.panel_tilt_deg,
            panel_azimuth_deg=request.panel_azimuth_deg,
            state=request.state,
        ),
        low_sunlight_reason="Sunlight intensity is below the recommended threshold.",
        low_capacity_reason="The region is too small to host a meaningful solar array.",
        success_reason="The region has enough area and sunlight for solar installation.",
    )

    debug_payload: dict[str, object] = {
        "model_source": estimate.model_source,
        "centroid": {
            "lat": round(centroid.lat, 6),
            "lon": round(centroid.lon, 6),
        },
        "weather_source": estimate.weather_source,
        "sunlight_intensity_kwh_m2_yr": round(estimate.sunlight_intensity_kwh_m2_yr, 2),
        "usable_area_m2": round(estimate.layout.usable_area_m2, 2),
        "panel_count": estimate.layout.panel_count,
        "installed_capacity_kw": round(estimate.layout.installed_capacity_kw, 2),
        "estimated_annual_output_kwh": round(estimate.estimated_annual_output_kwh, 2),
        "suitability_score": estimate.suitability_score,
        "suitable": estimate.suitable,
    }
    if estimate.climate is not None:
        debug_payload["climate"] = {
            "annual_temperature_c": round(
                estimate.climate["climate_annual_temperature_c"], 4
            ),
            "annual_cloud_cover_pct": round(
                estimate.climate["climate_annual_cloud_cover_pct"], 4
            ),
            "annual_relative_humidity_pct": round(
                estimate.climate["climate_annual_relative_humidity_pct"], 4
            ),
        }
    log_debug("solar-analysis", debug_payload)

    return SolarAnalysisResponse(
        area_m2=round(area_m2, 2),
        area_km2=round(area_km2, 4),
        centroid=Coordinate(lat=centroid.lat, lon=centroid.lon),
        sunlight_intensity_kwh_m2_yr=round(estimate.sunlight_intensity_kwh_m2_yr, 2),
        weather_source=estimate.weather_source,
        panel_count=estimate.layout.panel_count,
        installed_capacity_kw=round(estimate.layout.installed_capacity_kw, 2),
        estimated_annual_output_kwh=round(estimate.estimated_annual_output_kwh, 2),
        panel_cost_usd=round(estimate.cost.panel_cost_usd, 2),
        construction_cost_usd=round(estimate.cost.construction_cost_usd, 2),
        total_project_cost_usd=round(estimate.cost.total_project_cost_usd, 2),
        suitability_score=estimate.suitability_score,
        suitable=estimate.suitable,
        suitability_reason=estimate.suitability_reason,
        model_source=estimate.model_source,
    )
