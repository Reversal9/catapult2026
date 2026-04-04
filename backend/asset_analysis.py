from __future__ import annotations

import json
import math
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from geometry import polygon_area_and_centroid
from schemas import (
    AssetAnalysisRequest,
    AssetAnalysisResponse,
    Coordinate,
    DailyGenerationPoint,
)


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MINIMUM_USEFUL_PANEL_COUNT = 12


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def last_complete_year_period() -> tuple[str, str]:
    last_year = date.today().year - 1
    return f"{last_year}-01-01", f"{last_year}-12-31"


def fetch_open_meteo_archive(params: dict[str, str]) -> dict:
    url = f"{OPEN_METEO_ARCHIVE_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def score_explanation(score: float) -> str:
    if score >= 80:
        return "Strong fit. The site clears the main screening checks with room to spare."
    if score >= 60:
        return "Workable fit. The site looks usable, but some constraints still need closer review."
    if score >= 40:
        return "Borderline fit. The site has potential, but the limiting factors are significant."
    return "Weak fit. The site currently falls short on core screening checks."


def fetch_daily_solar_history(lat: float, lon: float) -> tuple[list[dict], str, str, str]:
    start_date, end_date = last_complete_year_period()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "shortwave_radiation_sum,sunshine_duration",
        "timezone": "auto",
    }

    try:
        payload = fetch_open_meteo_archive(params)
        daily = payload.get("daily", {})
        dates = daily.get("time", [])
        radiation = daily.get("shortwave_radiation_sum", [])
        sunshine = daily.get("sunshine_duration", [])
        if not dates or not radiation:
            raise ValueError("Open-Meteo solar history was incomplete.")
        return (
            [
                {
                    "date": day,
                    "radiation_kwh_m2": float(rad),
                    "sunshine_seconds": float(sun or 0),
                }
                for day, rad, sun in zip(dates, radiation, sunshine or [0] * len(dates))
            ],
            "open-meteo-historical",
            start_date,
            end_date,
        )
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        synthetic = []
        for index in range(365):
            seasonal = 4.2 + 2.5 * math.sin((2 * math.pi * index / 365.0) - 1.2)
            synthetic.append(
                {
                    "date": (date.fromisoformat(start_date) + timedelta(days=index)).isoformat(),
                    "radiation_kwh_m2": max(1.8, seasonal),
                    "sunshine_seconds": max(10_000.0, seasonal * 3_000),
                }
            )
        return synthetic, "fallback-proxy", start_date, end_date


def fetch_daily_wind_history(lat: float, lon: float) -> tuple[list[dict], str, str, str]:
    start_date, end_date = last_complete_year_period()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "wind_speed_100m",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }

    try:
        payload = fetch_open_meteo_archive(params)
        hourly = payload.get("hourly", {})
        timestamps = hourly.get("time", [])
        wind_speeds = hourly.get("wind_speed_100m", [])
        if not timestamps or not wind_speeds:
            raise ValueError("Open-Meteo wind history was incomplete.")

        daily_groups: dict[str, list[float]] = {}
        for timestamp, speed in zip(timestamps, wind_speeds):
            day = timestamp.split("T", 1)[0]
            daily_groups.setdefault(day, []).append(float(speed))

        return (
            [
                {
                    "date": day,
                    "wind_speed_mps": sum(values) / len(values),
                }
                for day, values in sorted(daily_groups.items())
            ],
            "open-meteo-historical",
            start_date,
            end_date,
        )
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        synthetic = []
        for index in range(365):
            seasonal = 6.1 + 1.4 * math.sin((2 * math.pi * index / 365.0) + 0.6)
            synthetic.append(
                {
                    "date": (date.fromisoformat(start_date) + timedelta(days=index)).isoformat(),
                    "wind_speed_mps": max(3.5, seasonal),
                }
            )
        return synthetic, "fallback-proxy", start_date, end_date


def analyze_asset_polygon(request: AssetAnalysisRequest) -> AssetAnalysisResponse:
    area_m2, centroid = polygon_area_and_centroid(request.points)
    area_km2 = area_m2 / 1_000_000.0

    if request.asset_type == "solar":
        return analyze_solar_asset(request, area_m2, area_km2, centroid)
    if request.asset_type == "wind":
        return analyze_wind_asset(request, area_m2, area_km2, centroid)
    return analyze_data_center_asset(request, area_m2, area_km2, centroid)


def analyze_solar_asset(
    request: AssetAnalysisRequest,
    area_m2: float,
    area_km2: float,
    centroid: Coordinate,
) -> AssetAnalysisResponse:
    spec = request.solar_spec
    daily_history, weather_source, start_date, end_date = fetch_daily_solar_history(
        centroid.lat,
        centroid.lon,
    )

    usable_area_m2 = area_m2 * spec.packing_efficiency
    panel_count = int(usable_area_m2 // spec.panel_area_m2)
    installed_capacity_kw = (panel_count * spec.panel_rating_w) / 1000.0
    panel_efficiency = spec.panel_rating_w / (1000.0 * spec.panel_area_m2)

    daily_generation = [
        DailyGenerationPoint(
            date=item["date"],
            generation_kwh=round(
                item["radiation_kwh_m2"]
                * usable_area_m2
                * panel_efficiency
                * spec.performance_ratio,
                2,
            ),
        )
        for item in daily_history
    ]
    annual_output = sum(point.generation_kwh for point in daily_generation)
    annual_radiation = sum(item["radiation_kwh_m2"] for item in daily_history)

    panel_cost_usd = panel_count * spec.panel_cost_usd
    construction_cost_usd = area_m2 * spec.construction_cost_per_m2_usd
    total_cost_usd = panel_cost_usd + construction_cost_usd

    intensity_score = clamp(
        (annual_radiation - 1_000.0) / 700.0 * 100.0,
        0.0,
        100.0,
    )
    capacity_score = clamp(panel_count / 200.0 * 100.0, 0.0, 100.0)
    feasibility_score = round(0.7 * intensity_score + 0.3 * capacity_score, 1)

    reasons = []
    if annual_radiation < spec.sunlight_threshold_kwh_m2_yr:
        reasons.append("Past-year sunlight was below the preferred level for a high-performing solar build.")
    if panel_count < MINIMUM_USEFUL_PANEL_COUNT:
        reasons.append("The selected region is too small for a practical solar layout with the chosen panel size.")
    if not reasons:
        reasons.append("The region has enough area and past-year sunlight to support a practical solar project.")

    suitable = annual_radiation >= spec.sunlight_threshold_kwh_m2_yr and panel_count >= MINIMUM_USEFUL_PANEL_COUNT

    return AssetAnalysisResponse(
        asset_type="solar",
        area_m2=round(area_m2, 2),
        area_km2=round(area_km2, 4),
        centroid=Coordinate(lat=centroid.lat, lon=centroid.lon),
        asset_count=panel_count,
        installed_capacity_kw=round(installed_capacity_kw, 2),
        estimated_annual_output_kwh=round(annual_output, 2),
        estimated_installation_cost_usd=round(total_cost_usd, 2),
        feasibility_score=feasibility_score,
        score_explanation=score_explanation(feasibility_score),
        suitable=suitable,
        suitability_reason=" ".join(reasons),
        weather_source=weather_source,
        trend_period_start=start_date,
        trend_period_end=end_date,
        daily_generation_kwh=daily_generation,
        metadata={
            "preset_name": request.preset_name,
            "panel_area_m2": spec.panel_area_m2,
            "panel_rating_w": spec.panel_rating_w,
            "panel_cost_usd": spec.panel_cost_usd,
            "packing_efficiency": spec.packing_efficiency,
            "performance_ratio": spec.performance_ratio,
        },
    )


def analyze_wind_asset(
    request: AssetAnalysisRequest,
    area_m2: float,
    area_km2: float,
    centroid: Coordinate,
) -> AssetAnalysisResponse:
    spec = request.wind_spec
    daily_history, weather_source, start_date, end_date = fetch_daily_wind_history(
        centroid.lat,
        centroid.lon,
    )

    turbine_count = max(0, int(area_m2 // spec.spacing_area_m2))
    daily_generation = []
    for item in daily_history:
        speed = item["wind_speed_mps"]
        capacity_factor = clamp(0.35 * (speed / 7.0) ** 2.5, 0.03, 0.65)
        daily_generation.append(
            DailyGenerationPoint(
                date=item["date"],
                generation_kwh=round(
                    turbine_count * spec.turbine_rating_kw * 24.0 * capacity_factor,
                    2,
                ),
            )
        )

    annual_output = sum(point.generation_kwh for point in daily_generation)
    mean_speed = (
        sum(item["wind_speed_mps"] for item in daily_history) / max(len(daily_history), 1)
    )
    installed_capacity_kw = turbine_count * spec.turbine_rating_kw
    estimated_cost = turbine_count * spec.turbine_cost_usd + area_m2 * 16.0

    speed_score = clamp(
        (mean_speed - spec.minimum_viable_wind_speed_mps) / 3.0 * 100.0,
        0.0,
        100.0,
    )
    count_score = clamp(turbine_count / 6.0 * 100.0, 0.0, 100.0)
    feasibility_score = round(0.65 * speed_score + 0.35 * count_score, 1)

    reasons = []
    if mean_speed < spec.minimum_viable_wind_speed_mps:
        reasons.append("Past-year wind speeds were below the preferred level for this turbine setup.")
    if turbine_count < 1:
        reasons.append("The region is too small to fit a practical turbine spacing layout.")
    if not reasons:
        reasons.append("The region has enough space and past-year wind conditions for a practical turbine layout.")

    suitable = mean_speed >= spec.minimum_viable_wind_speed_mps and turbine_count >= 1

    return AssetAnalysisResponse(
        asset_type="wind",
        area_m2=round(area_m2, 2),
        area_km2=round(area_km2, 4),
        centroid=Coordinate(lat=centroid.lat, lon=centroid.lon),
        asset_count=turbine_count,
        installed_capacity_kw=round(installed_capacity_kw, 2),
        estimated_annual_output_kwh=round(annual_output, 2),
        estimated_installation_cost_usd=round(estimated_cost, 2),
        feasibility_score=feasibility_score,
        score_explanation=score_explanation(feasibility_score),
        suitable=suitable,
        suitability_reason=" ".join(reasons),
        weather_source=weather_source,
        trend_period_start=start_date,
        trend_period_end=end_date,
        daily_generation_kwh=daily_generation,
        metadata={
            "preset_name": request.preset_name,
            "turbine_rating_kw": spec.turbine_rating_kw,
            "turbine_cost_usd": spec.turbine_cost_usd,
            "spacing_area_m2": spec.spacing_area_m2,
            "minimum_viable_wind_speed_mps": spec.minimum_viable_wind_speed_mps,
            "mean_wind_speed_mps": round(mean_speed, 2),
        },
    )


def analyze_data_center_asset(
    request: AssetAnalysisRequest,
    area_m2: float,
    area_km2: float,
    centroid: Coordinate,
) -> AssetAnalysisResponse:
    spec = request.data_center_spec
    installed_capacity_kw = area_m2 * spec.power_density_kw_per_m2
    estimated_cost = (
        area_m2 * spec.construction_cost_per_m2_usd
        + installed_capacity_kw * spec.fit_out_cost_per_kw_usd
    )
    feasibility_score = round(
        clamp((area_m2 / 20_000.0) * 100.0, 10.0, 92.0),
        1,
    )
    suitable = area_m2 >= 8_000
    reason = (
        "The region is large enough to support a compact data center campus footprint."
        if suitable
        else "The region is likely too small for a practical data center campus once setbacks and support space are included."
    )

    return AssetAnalysisResponse(
        asset_type="data_center",
        area_m2=round(area_m2, 2),
        area_km2=round(area_km2, 4),
        centroid=Coordinate(lat=centroid.lat, lon=centroid.lon),
        asset_count=1 if suitable else 0,
        installed_capacity_kw=round(installed_capacity_kw, 2),
        estimated_annual_output_kwh=None,
        estimated_installation_cost_usd=round(estimated_cost, 2),
        feasibility_score=feasibility_score,
        score_explanation=score_explanation(feasibility_score),
        suitable=suitable,
        suitability_reason=reason,
        weather_source="not-applicable",
        trend_period_start=f"{date.today().year - 1}-01-01",
        trend_period_end=f"{date.today().year - 1}-12-31",
        daily_generation_kwh=[],
        metadata={
            "preset_name": request.preset_name,
            "power_density_kw_per_m2": spec.power_density_kw_per_m2,
            "construction_cost_per_m2_usd": spec.construction_cost_per_m2_usd,
            "fit_out_cost_per_kw_usd": spec.fit_out_cost_per_kw_usd,
            "note": "Data centers consume power rather than generate it, so no daily generation trend is shown.",
        },
    )
