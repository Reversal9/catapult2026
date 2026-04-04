export const titleCaseAssetType = (value) =>
  value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export const mapAssetResult = (payload, config) => ({
  type: payload.asset_type,
  label: titleCaseAssetType(payload.asset_type),
  areaKm2: payload.area_km2,
  assetCount: payload.asset_count,
  installedCapacityKw: payload.installed_capacity_kw,
  annualMWh: payload.estimated_annual_output_kwh
    ? payload.estimated_annual_output_kwh / 1000
    : null,
  totalCost: payload.estimated_installation_cost_usd,
  feasibilityScore: payload.feasibility_score,
  scoreExplanation: payload.score_explanation,
  suitable: payload.suitable,
  suitabilityReason: payload.suitability_reason,
  weatherSource: payload.weather_source,
  trendPeriodStart: payload.trend_period_start,
  trendPeriodEnd: payload.trend_period_end,
  dailyGeneration: payload.daily_generation_kwh,
  metadata: payload.metadata,
  presetName: config.presetName,
});
