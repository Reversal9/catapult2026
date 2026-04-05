from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from geometry import polygon_area_and_centroid
try:
    from model_predictor import get_predictor
except Exception:  # pragma: no cover - optional ML dependency missing in tests
    def get_predictor():
        return None
from schemas import Coordinate, SolarAnalysisRequest, SolarAnalysisResponse

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
DEFAULT_COST_STATE = "CA"


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


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


def _suitability_from_era5(
    ghi_annual: float,
    cloud_cover_pct: float,
    annual_temp_c: float,
) -> float:
    """
    ERA5-grounded suitability score [0–100].

    Components:
      60% — GHI (primary solar resource driver)
      30% — cloud cover (lower cloud = more direct radiation)
      10% — temperature (panels lose ~0.4 %/°C above 25 °C)
    """
    ghi_score = clamp((ghi_annual - 900.0) / 800.0 * 100.0, 0.0, 100.0)
    cloud_score = clamp((80.0 - cloud_cover_pct) / 80.0 * 100.0, 0.0, 100.0)
    temp_penalty = max(0.0, (annual_temp_c - 25.0) * 2.0)
    temp_score = clamp(100.0 - temp_penalty, 0.0, 100.0)
    return round(0.6 * ghi_score + 0.3 * cloud_score + 0.1 * temp_score, 1)


def _suitability_from_ghi(ghi_annual: float, panel_count: int) -> float:
    """Physics-fallback suitability when ERA5 data is unavailable."""
    ghi_score = clamp((ghi_annual - 900.0) / 800.0 * 100.0, 0.0, 100.0)
    capacity_score = clamp(panel_count / 200.0 * 100.0, 0.0, 100.0)
    return round(0.7 * ghi_score + 0.3 * capacity_score, 1)


def _estimate_panel_dimensions_from_area(panel_area_m2: float) -> tuple[float, float]:
    """
    Estimate panel length and width from area assuming standard aspect ratio.
    Most solar panels have aspect ratio around 1.7:1 (length:width).
    """
    # Assume aspect ratio of 1.7:1 (typical for solar panels)
    aspect_ratio = 1.7
    # width = sqrt(area / aspect_ratio)
    width_m = (panel_area_m2 / aspect_ratio) ** 0.5
    length_m = width_m * aspect_ratio
    return length_m, width_m


def _calculate_costs_with_cost_module(
    area_m2: float,
    panel_area_m2: float,
    panel_rating_w: float,
    packing_efficiency: float,
    performance_ratio: float,
    sunlight_intensity_kwh_m2_yr: float,
    state: str = DEFAULT_COST_STATE,
) -> tuple[float, float, float]:
    """
    Calculate costs using the cost.py module.
    Returns: (panel_cost_usd, construction_cost_usd, total_project_cost_usd)
    """
    if not COST_MODULE_AVAILABLE or COST_FUNCTION is None:
        raise ImportError("Cost module not available")

    # Convert sunlight intensity from kWh/m²/yr to kWh/m²/day for cost module
    ghi_kwh_m2_day = sunlight_intensity_kwh_m2_yr / 365.0

    # Estimate panel dimensions from area
    panel_length_m, panel_width_m = _estimate_panel_dimensions_from_area(panel_area_m2)

    # Create panel specs in the format expected by cost.py
    panel_specs = {
        "length_m": panel_length_m,
        "width_m": panel_width_m,
        "STC_W": panel_rating_w,
    }

    try:
        # Use the cost pipeline
        cost_result = COST_FUNCTION(
            area_m2=area_m2,
            panel_specs=panel_specs,
            state=state,
            year=2026,  # Current year for ITC calculation
            ghi_kwh_m2_day=ghi_kwh_m2_day,
            packing_factor=packing_efficiency,
            performance_ratio=performance_ratio,
            state_rebate_usd=0.0,  # No state rebate by default
        )

        # Extract costs from the result
        incentives = cost_result["layer_4_incentives"]

        # The cost module produces a project-level cost, not an equipment/install split.
        # Keep the existing API shape by allocating the pipeline-derived total.
        # For now, use a simple allocation: assume panels are 40% of total cost
        # This is a rough estimate - in reality it varies by project
        total_cost = incentives["net_cost_usd"]
        panel_cost = total_cost * 0.4
        construction_cost = total_cost * 0.6

        return panel_cost, construction_cost, total_cost

    except Exception as e:
        # If cost module fails, fall back to simple calculation
        raise ValueError(f"Cost module failed: {e}")


def analyze_solar_polygon(request: SolarAnalysisRequest) -> SolarAnalysisResponse:
    area_m2, centroid = polygon_area_and_centroid(request.points)
    area_km2 = area_m2 / 1_000_000.0
    sunlight_intensity_kwh_m2_yr, weather_source = fetch_annual_solar_intensity(
        centroid.lat,
        centroid.lon,
    )

    usable_area_m2 = area_m2 * request.packing_efficiency
    panel_count = int(usable_area_m2 // request.panel_area_m2)
    installed_capacity_kw = (panel_count * request.panel_rating_w) / 1000.0

    # --- Energy estimate: RF model if available, physics formula as fallback ---
    predictor = get_predictor()
    if predictor is not None:
        try:
            estimated_annual_output_kwh, climate = predictor.predict(
                lat=centroid.lat,
                lon=centroid.lon,
                usable_area_m2=usable_area_m2,
                panel_tilt_deg=request.panel_tilt_deg,
                panel_azimuth_deg=request.panel_azimuth_deg,
            )
            suitability_score = _suitability_from_era5(
                ghi_annual=sunlight_intensity_kwh_m2_yr,
                cloud_cover_pct=climate["climate_annual_cloud_cover_pct"],
                annual_temp_c=climate["climate_annual_temperature_c"],
            )
            model_source = getattr(predictor, "model_name", "random-forest")
        except Exception:
            predictor = None

    if predictor is None:
        panel_efficiency = request.panel_rating_w / (1000.0 * request.panel_area_m2)
        estimated_annual_output_kwh = (
            sunlight_intensity_kwh_m2_yr
            * usable_area_m2
            * panel_efficiency
            * request.performance_ratio
        )
        suitability_score = _suitability_from_ghi(sunlight_intensity_kwh_m2_yr, panel_count)
        model_source = "physics-fallback"

    # --- Cost ---
    # Use the cost pipeline whenever it is available. If the request does not
    # include a state, fall back to a deterministic default so frontend callers
    # still receive pipeline-based costs.
    use_cost_module = COST_MODULE_AVAILABLE

    if use_cost_module:
        try:
            state_str = request.state or DEFAULT_COST_STATE
            panel_cost_usd, construction_cost_usd, total_project_cost_usd = _calculate_costs_with_cost_module(
                area_m2=area_m2,
                panel_area_m2=request.panel_area_m2,
                panel_rating_w=request.panel_rating_w,
                packing_efficiency=request.packing_efficiency,
                performance_ratio=request.performance_ratio,
                sunlight_intensity_kwh_m2_yr=sunlight_intensity_kwh_m2_yr,
                state=state_str
            )
        except Exception as e:
            # Fall back to simple calculation if cost module fails
            print(f"Cost module failed, falling back to simple calculation: {e}")
            panel_cost_usd = panel_count * request.panel_cost_usd
            construction_cost_usd = area_m2 * request.construction_cost_per_m2_usd
            total_project_cost_usd = panel_cost_usd + construction_cost_usd
    else:
        # Use simple calculation if cost module not available or no state provided
        panel_cost_usd = panel_count * request.panel_cost_usd
        construction_cost_usd = area_m2 * request.construction_cost_per_m2_usd
        total_project_cost_usd = panel_cost_usd + construction_cost_usd

    # --- Suitability verdict ---
    reasons = []
    if sunlight_intensity_kwh_m2_yr < request.sunlight_threshold_kwh_m2_yr:
        reasons.append("Sunlight intensity is below the recommended threshold.")
    if panel_count < MINIMUM_USEFUL_PANEL_COUNT:
        reasons.append("The region is too small to host a meaningful solar array.")
    if not reasons:
        reasons.append("The region has enough area and sunlight for solar installation.")

    suitable = (
        sunlight_intensity_kwh_m2_yr >= request.sunlight_threshold_kwh_m2_yr
        and panel_count >= MINIMUM_USEFUL_PANEL_COUNT
    )

    return SolarAnalysisResponse(
        area_m2=round(area_m2, 2),
        area_km2=round(area_km2, 4),
        centroid=Coordinate(lat=centroid.lat, lon=centroid.lon),
        sunlight_intensity_kwh_m2_yr=round(sunlight_intensity_kwh_m2_yr, 2),
        weather_source=weather_source,
        panel_count=panel_count,
        installed_capacity_kw=round(installed_capacity_kw, 2),
        estimated_annual_output_kwh=round(estimated_annual_output_kwh, 2),
        panel_cost_usd=round(panel_cost_usd, 2),
        construction_cost_usd=round(construction_cost_usd, 2),
        total_project_cost_usd=round(total_project_cost_usd, 2),
        suitability_score=suitability_score,
        suitable=suitable,
        suitability_reason=" ".join(reasons),
        model_source=model_source,
    )