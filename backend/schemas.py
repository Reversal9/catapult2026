from __future__ import annotations

from pydantic import BaseModel, Field


DEFAULT_SOLAR_PANEL_AREA_M2 = 2.0
DEFAULT_PANEL_RATING_W = 420.0
DEFAULT_PANEL_COST_USD = 260.0
DEFAULT_CONSTRUCTION_COST_PER_M2_USD = 140.0
DEFAULT_PACKING_EFFICIENCY = 0.75
DEFAULT_PERFORMANCE_RATIO = 0.8
DEFAULT_SUNLIGHT_THRESHOLD_KWH_M2_YR = 1_400.0
DEFAULT_PANEL_TILT_DEG = 20.0      # median from EIA solar dataset
DEFAULT_PANEL_AZIMUTH_DEG = 180.0  # south-facing, standard US optimum


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class SolarAnalysisRequest(BaseModel):
    points: list[Coordinate] = Field(...)
    panel_area_m2: float = Field(default=DEFAULT_SOLAR_PANEL_AREA_M2, gt=0)
    panel_rating_w: float = Field(default=DEFAULT_PANEL_RATING_W, gt=0)
    panel_cost_usd: float = Field(default=DEFAULT_PANEL_COST_USD, gt=0)
    construction_cost_per_m2_usd: float = Field(
        default=DEFAULT_CONSTRUCTION_COST_PER_M2_USD,
        gt=0,
    )
    packing_efficiency: float = Field(default=DEFAULT_PACKING_EFFICIENCY, gt=0, le=1)
    performance_ratio: float = Field(default=DEFAULT_PERFORMANCE_RATIO, gt=0, le=1)
    sunlight_threshold_kwh_m2_yr: float = Field(
        default=DEFAULT_SUNLIGHT_THRESHOLD_KWH_M2_YR,
        gt=0,
    )
    panel_tilt_deg: float = Field(default=DEFAULT_PANEL_TILT_DEG, ge=0, le=90)
    panel_azimuth_deg: float = Field(default=DEFAULT_PANEL_AZIMUTH_DEG, ge=0, le=360)


class SolarAnalysisResponse(BaseModel):
    area_m2: float
    area_km2: float
    centroid: Coordinate
    sunlight_intensity_kwh_m2_yr: float
    weather_source: str
    panel_count: int
    installed_capacity_kw: float
    estimated_annual_output_kwh: float
    panel_cost_usd: float
    construction_cost_usd: float
    total_project_cost_usd: float
    suitability_score: float
    suitable: bool
    suitability_reason: str
    model_source: str  # "random-forest", "physics-fallback"