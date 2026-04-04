from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DEFAULT_SOLAR_PANEL_AREA_M2 = 2.0
DEFAULT_PANEL_RATING_W = 420.0
DEFAULT_PANEL_COST_USD = 260.0
DEFAULT_CONSTRUCTION_COST_PER_M2_USD = 140.0
DEFAULT_PACKING_EFFICIENCY = 0.75
DEFAULT_PERFORMANCE_RATIO = 0.8
DEFAULT_SUNLIGHT_THRESHOLD_KWH_M2_YR = 1_400.0
DEFAULT_WIND_TURBINE_RATING_KW = 3_500.0
DEFAULT_WIND_TURBINE_COST_USD = 1_850_000.0
DEFAULT_WIND_SPACING_AREA_M2 = 45_000.0
DEFAULT_WIND_MIN_SPEED_MPS = 5.5
DEFAULT_DATA_CENTER_POWER_DENSITY_KW_PER_M2 = 0.055
DEFAULT_DATA_CENTER_COST_PER_M2_USD = 280.0
DEFAULT_DATA_CENTER_FIT_OUT_COST_PER_KW_USD = 4_500.0


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


class DailyGenerationPoint(BaseModel):
    date: str
    generation_kwh: float


class SolarAssetSpec(BaseModel):
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


class WindAssetSpec(BaseModel):
    turbine_rating_kw: float = Field(default=DEFAULT_WIND_TURBINE_RATING_KW, gt=0)
    turbine_cost_usd: float = Field(default=DEFAULT_WIND_TURBINE_COST_USD, gt=0)
    spacing_area_m2: float = Field(default=DEFAULT_WIND_SPACING_AREA_M2, gt=1000)
    minimum_viable_wind_speed_mps: float = Field(default=DEFAULT_WIND_MIN_SPEED_MPS, gt=0)


class DataCenterAssetSpec(BaseModel):
    power_density_kw_per_m2: float = Field(
        default=DEFAULT_DATA_CENTER_POWER_DENSITY_KW_PER_M2,
        gt=0,
    )
    construction_cost_per_m2_usd: float = Field(
        default=DEFAULT_DATA_CENTER_COST_PER_M2_USD,
        gt=0,
    )
    fit_out_cost_per_kw_usd: float = Field(
        default=DEFAULT_DATA_CENTER_FIT_OUT_COST_PER_KW_USD,
        gt=0,
    )


class AssetAnalysisRequest(BaseModel):
    asset_type: Literal["solar", "wind", "data_center"] = Field(...)
    points: list[Coordinate] = Field(...)
    preset_name: str | None = Field(default=None, max_length=120)
    solar_spec: SolarAssetSpec = Field(default_factory=SolarAssetSpec)
    wind_spec: WindAssetSpec = Field(default_factory=WindAssetSpec)
    data_center_spec: DataCenterAssetSpec = Field(default_factory=DataCenterAssetSpec)


class AssetAnalysisResponse(BaseModel):
    asset_type: Literal["solar", "wind", "data_center"]
    area_m2: float
    area_km2: float
    centroid: Coordinate
    asset_count: int | None = None
    installed_capacity_kw: float | None = None
    estimated_annual_output_kwh: float | None = None
    estimated_installation_cost_usd: float
    feasibility_score: float
    score_explanation: str
    suitable: bool
    suitability_reason: str
    weather_source: str
    trend_period_start: str
    trend_period_end: str
    daily_generation_kwh: list[DailyGenerationPoint]
    metadata: dict


class BoundingBox(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


class InfrastructureAnalysisRequest(BaseModel):
    points: list[Coordinate] = Field(...)
    cell_size_m: float = Field(default=300.0, ge=100.0, le=2_000.0)
    imagery_provider: Literal["usgs", "mapbox", "google", "sentinel", "none"] = Field(
        default="usgs"
    )
    segmentation_backend: Literal[
        "auto",
        "rule_based",
        "unet",
        "mask_rcnn",
        "hybrid",
    ] = Field(default="auto")
    terrain_provider: Literal["opentopodata", "proxy"] = Field(default="opentopodata")
    include_debug_layers: bool = Field(default=False)


class CandidateRegion(BaseModel):
    id: str
    use_type: Literal["solar", "wind", "data_center"]
    polygon: list[Coordinate]
    area_m2: float
    feasibility_score: float
    reasoning: list[str]
    estimated_annual_output_kwh: float | None = None
    estimated_installation_cost_usd: float
    metadata: dict


class InfrastructureDataSources(BaseModel):
    imagery: str
    vector_data: str
    segmentation: str
    terrain: str


class InfrastructureAnalysisResponse(BaseModel):
    area_m2: float
    bbox: BoundingBox
    centroid: Coordinate
    subdivisions_evaluated: int
    candidates: list[CandidateRegion]
    data_sources: InfrastructureDataSources
    pipeline_notes: list[str]
