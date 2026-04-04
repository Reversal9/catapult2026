from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from model_predictor import get_predictor

# Try to import cost module, but handle if it's not available
try:
    from cost.cost import estimate_solar_project_cost

    COST_MODULE_AVAILABLE = True
    COST_FUNCTION = estimate_solar_project_cost
except ImportError:
    COST_MODULE_AVAILABLE = False
    COST_FUNCTION = None


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MINIMUM_USEFUL_PANEL_COUNT = 12
LOGGER = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class SolarProjectInputs:
    area_m2: float
    centroid_lat: float
    centroid_lon: float
    panel_area_m2: float
    panel_rating_w: float
    panel_cost_usd: float
    construction_cost_per_m2_usd: float
    packing_efficiency: float
    performance_ratio: float
    sunlight_threshold_kwh_m2_yr: float
    panel_tilt_deg: float
    panel_azimuth_deg: float
    state: str | None = None


@dataclass(frozen=True)
class SolarLayout:
    usable_area_m2: float
    panel_count: int
    installed_capacity_kw: float


@dataclass(frozen=True)
class SolarCostBreakdown:
    panel_cost_usd: float
    construction_cost_usd: float
    total_project_cost_usd: float


@dataclass(frozen=True)
class SolarProjectEstimate:
    sunlight_intensity_kwh_m2_yr: float
    weather_source: str
    layout: SolarLayout
    estimated_annual_output_kwh: float
    suitability_score: float
    suitable: bool
    suitability_reason: str
    model_source: str
    cost: SolarCostBreakdown
    climate: dict[str, float] | None


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def log_debug(tag: str, payload: dict[str, object]) -> None:
    LOGGER.info("[%s] %s", tag, json.dumps(payload, sort_keys=True))


def fetch_annual_solar_intensity(lat: float, lon: float) -> tuple[float, str]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "hourly": "shortwave_radiation",
        "timezone": "auto",
    }
    url = f"{OPEN_METEO_ARCHIVE_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        hourly = payload.get("hourly", {})
        radiation_values = hourly.get("shortwave_radiation", [])
        if not radiation_values:
            raise ValueError("Open-Meteo response did not include shortwave radiation.")
        return sum(float(value) for value in radiation_values) / 1000.0, "open-meteo"
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        fallback = max(900.0, 2_050.0 - 18.0 * abs(lat))
        return fallback, "fallback-proxy"


def build_solar_layout(inputs: SolarProjectInputs) -> SolarLayout:
    usable_area_m2 = inputs.area_m2 * inputs.packing_efficiency
    panel_count = int(usable_area_m2 // inputs.panel_area_m2)
    installed_capacity_kw = (panel_count * inputs.panel_rating_w) / 1000.0
    return SolarLayout(
        usable_area_m2=usable_area_m2,
        panel_count=panel_count,
        installed_capacity_kw=installed_capacity_kw,
    )


def _suitability_from_era5(
    ghi_annual: float,
    cloud_cover_pct: float,
    annual_temp_c: float,
) -> float:
    ghi_score = clamp((ghi_annual - 900.0) / 800.0 * 100.0, 0.0, 100.0)
    cloud_score = clamp((80.0 - cloud_cover_pct) / 80.0 * 100.0, 0.0, 100.0)
    temp_penalty = max(0.0, (annual_temp_c - 25.0) * 2.0)
    temp_score = clamp(100.0 - temp_penalty, 0.0, 100.0)
    return round(0.6 * ghi_score + 0.3 * cloud_score + 0.1 * temp_score, 1)


def _suitability_from_ghi(ghi_annual: float, panel_count: int) -> float:
    ghi_score = clamp((ghi_annual - 900.0) / 800.0 * 100.0, 0.0, 100.0)
    capacity_score = clamp(panel_count / 200.0 * 100.0, 0.0, 100.0)
    return round(0.7 * ghi_score + 0.3 * capacity_score, 1)


def _estimate_panel_dimensions_from_area(panel_area_m2: float) -> tuple[float, float]:
    aspect_ratio = 1.7
    width_m = (panel_area_m2 / aspect_ratio) ** 0.5
    length_m = width_m * aspect_ratio
    return length_m, width_m


def _calculate_costs_with_cost_module(
    inputs: SolarProjectInputs,
    sunlight_intensity_kwh_m2_yr: float,
) -> SolarCostBreakdown:
    if not COST_MODULE_AVAILABLE or COST_FUNCTION is None:
        raise ImportError("Cost module not available")

    ghi_kwh_m2_day = sunlight_intensity_kwh_m2_yr / 365.0
    panel_length_m, panel_width_m = _estimate_panel_dimensions_from_area(
        inputs.panel_area_m2
    )
    panel_specs = {
        "length_m": panel_length_m,
        "width_m": panel_width_m,
        "STC_W": inputs.panel_rating_w,
    }

    try:
        cost_result = COST_FUNCTION(
            area_m2=inputs.area_m2,
            panel_specs=panel_specs,
            state=inputs.state or "CA",
            year=2026,
            ghi_kwh_m2_day=ghi_kwh_m2_day,
            packing_factor=inputs.packing_efficiency,
            performance_ratio=inputs.performance_ratio,
            state_rebate_usd=0.0,
        )
        incentives = cost_result["layer_4_incentives"]
        total_cost = float(incentives["net_cost_usd"])
        return SolarCostBreakdown(
            panel_cost_usd=total_cost * 0.4,
            construction_cost_usd=total_cost * 0.6,
            total_project_cost_usd=total_cost,
        )
    except Exception as exc:
        raise ValueError(f"Cost module failed: {exc}") from exc


def estimate_solar_costs(
    inputs: SolarProjectInputs,
    layout: SolarLayout,
    sunlight_intensity_kwh_m2_yr: float,
) -> SolarCostBreakdown:
    use_cost_module = COST_MODULE_AVAILABLE and inputs.state is not None
    if use_cost_module:
        try:
            return _calculate_costs_with_cost_module(
                inputs=inputs,
                sunlight_intensity_kwh_m2_yr=sunlight_intensity_kwh_m2_yr,
            )
        except Exception:
            pass

    panel_cost_usd = layout.panel_count * inputs.panel_cost_usd
    construction_cost_usd = inputs.area_m2 * inputs.construction_cost_per_m2_usd
    return SolarCostBreakdown(
        panel_cost_usd=panel_cost_usd,
        construction_cost_usd=construction_cost_usd,
        total_project_cost_usd=panel_cost_usd + construction_cost_usd,
    )


def estimate_solar_energy(
    inputs: SolarProjectInputs,
    layout: SolarLayout,
    sunlight_intensity_kwh_m2_yr: float,
) -> tuple[float, float, str, dict[str, float] | None]:
    predictor = get_predictor()
    if predictor is not None:
        estimated_annual_output_kwh, climate = predictor.predict(
            lat=inputs.centroid_lat,
            lon=inputs.centroid_lon,
            usable_area_m2=layout.usable_area_m2,
            panel_tilt_deg=inputs.panel_tilt_deg,
            panel_azimuth_deg=inputs.panel_azimuth_deg,
        )
        suitability_score = _suitability_from_era5(
            ghi_annual=sunlight_intensity_kwh_m2_yr,
            cloud_cover_pct=climate["climate_annual_cloud_cover_pct"],
            annual_temp_c=climate["climate_annual_temperature_c"],
        )
        return estimated_annual_output_kwh, suitability_score, predictor.model_name, climate

    panel_efficiency = inputs.panel_rating_w / (1000.0 * inputs.panel_area_m2)
    estimated_annual_output_kwh = (
        sunlight_intensity_kwh_m2_yr
        * layout.usable_area_m2
        * panel_efficiency
        * inputs.performance_ratio
    )
    suitability_score = _suitability_from_ghi(
        sunlight_intensity_kwh_m2_yr,
        layout.panel_count,
    )
    return estimated_annual_output_kwh, suitability_score, "physics-fallback", None


def build_suitability_reason(
    sunlight_intensity_kwh_m2_yr: float,
    sunlight_threshold_kwh_m2_yr: float,
    panel_count: int,
    low_sunlight_reason: str,
    low_capacity_reason: str,
    success_reason: str,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if sunlight_intensity_kwh_m2_yr < sunlight_threshold_kwh_m2_yr:
        reasons.append(low_sunlight_reason)
    if panel_count < MINIMUM_USEFUL_PANEL_COUNT:
        reasons.append(low_capacity_reason)
    if not reasons:
        reasons.append(success_reason)

    suitable = (
        sunlight_intensity_kwh_m2_yr >= sunlight_threshold_kwh_m2_yr
        and panel_count >= MINIMUM_USEFUL_PANEL_COUNT
    )
    return suitable, " ".join(reasons)


def analyze_solar_project(
    inputs: SolarProjectInputs,
    *,
    sunlight_intensity_kwh_m2_yr: float | None = None,
    weather_source: str | None = None,
    low_sunlight_reason: str,
    low_capacity_reason: str,
    success_reason: str,
) -> SolarProjectEstimate:
    if sunlight_intensity_kwh_m2_yr is None or weather_source is None:
        sunlight_intensity_kwh_m2_yr, weather_source = fetch_annual_solar_intensity(
            inputs.centroid_lat,
            inputs.centroid_lon,
        )

    layout = build_solar_layout(inputs)
    estimated_annual_output_kwh, suitability_score, model_source, climate = (
        estimate_solar_energy(
            inputs=inputs,
            layout=layout,
            sunlight_intensity_kwh_m2_yr=sunlight_intensity_kwh_m2_yr,
        )
    )
    cost = estimate_solar_costs(
        inputs=inputs,
        layout=layout,
        sunlight_intensity_kwh_m2_yr=sunlight_intensity_kwh_m2_yr,
    )
    suitable, suitability_reason = build_suitability_reason(
        sunlight_intensity_kwh_m2_yr=sunlight_intensity_kwh_m2_yr,
        sunlight_threshold_kwh_m2_yr=inputs.sunlight_threshold_kwh_m2_yr,
        panel_count=layout.panel_count,
        low_sunlight_reason=low_sunlight_reason,
        low_capacity_reason=low_capacity_reason,
        success_reason=success_reason,
    )

    return SolarProjectEstimate(
        sunlight_intensity_kwh_m2_yr=sunlight_intensity_kwh_m2_yr,
        weather_source=weather_source,
        layout=layout,
        estimated_annual_output_kwh=estimated_annual_output_kwh,
        suitability_score=suitability_score,
        suitable=suitable,
        suitability_reason=suitability_reason,
        model_source=model_source,
        cost=cost,
        climate=climate,
    )
