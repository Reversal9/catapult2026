import { regionCenter } from "../utils/geo";

export const titleCaseUseType = (value) =>
  value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export const mapInfrastructureResult = (payload, settings) => {
  const candidates = payload.candidates.map((candidate) => {
    const polygon = candidate.polygon.map((point) => [point.lat, point.lon]);
    const validRegionPolygons = (
      candidate.metadata?.valid_region_polygons ?? [candidate.polygon]
    ).map((poly) => poly.map((point) => [point.lat, point.lon]));
    const packingBlockPolygons = (
      candidate.metadata?.packing_block_polygons ?? []
    ).map((poly) => poly.map((point) => [point.lat, point.lon]));
    const placementPolygons = (
      candidate.metadata?.placement_polygons ?? []
    ).map((poly) => poly.map((point) => [point.lat, point.lon]));
    return {
      id: candidate.id,
      useType: candidate.use_type,
      useLabel: titleCaseUseType(candidate.use_type),
      polygon,
      validRegionPolygons,
      packingBlockPolygons,
      placementPolygons,
      center: regionCenter({ type: "polygon", points: polygon }),
      areaKm2: candidate.area_m2 / 1_000_000,
      feasibilityScore: candidate.feasibility_score,
      reasoning: candidate.reasoning,
      estimatedAnnualOutputKwh: candidate.estimated_annual_output_kwh,
      estimatedInstallationCostUsd: candidate.estimated_installation_cost_usd,
      metadata: candidate.metadata,
    };
  });

  return {
    type: "infrastructure",
    label: "Infrastructure siting",
    areaKm2: payload.area_m2 / 1_000_000,
    subdivisionsEvaluated: payload.subdivisions_evaluated,
    candidateCount: candidates.length,
    candidates,
    dataSources: payload.data_sources,
    notes: payload.pipeline_notes,
    imageryProvider: settings.imageryProvider,
    segmentationBackend: settings.segmentationBackend,
    cellSizeMeters: settings.cellSizeMeters,
  };
};

export const mapSolarSitingResult = (payload, settings, config) => {
  const allCandidates = payload.candidates.map((candidate) => {
    const polygon = candidate.polygon.map((point) => [point.lat, point.lon]);
    const validRegionPolygons = (
      candidate.metadata?.valid_region_polygons ?? [candidate.polygon]
    ).map((poly) => poly.map((point) => [point.lat, point.lon]));
    const packingBlockPolygons = (
      candidate.metadata?.packing_block_polygons ?? []
    ).map((poly) => poly.map((point) => [point.lat, point.lon]));
    const placementPolygons = (
      candidate.metadata?.placement_polygons ?? []
    ).map((poly) => poly.map((point) => [point.lat, point.lon]));
    return {
      id: candidate.id,
      useType: candidate.use_type,
      useLabel: titleCaseUseType(candidate.use_type),
      polygon,
      validRegionPolygons,
      packingBlockPolygons,
      placementPolygons,
      center: regionCenter({ type: "polygon", points: polygon }),
      areaKm2: candidate.area_m2 / 1_000_000,
      feasibilityScore: candidate.feasibility_score,
      reasoning: candidate.reasoning,
      estimatedAnnualOutputKwh: candidate.estimated_annual_output_kwh,
      estimatedInstallationCostUsd: candidate.estimated_installation_cost_usd,
      metadata: candidate.metadata,
    };
  });

  const solarCandidates = allCandidates.filter(
    (candidate) => candidate.useType === "solar",
  );
  const validAreaKm2 = solarCandidates.reduce(
    (sum, candidate) => sum + candidate.areaKm2,
    0,
  );
  const installedCapacityKw = solarCandidates.reduce(
    (sum, candidate) =>
      sum + (candidate.metadata.installed_capacity_kw ?? 0),
    0,
  );
  const panelCount = solarCandidates.reduce(
    (sum, candidate) => sum + (candidate.metadata.panel_count ?? 0),
    0,
  );
  const estimatedAnnualOutputKwh = solarCandidates.reduce(
    (sum, candidate) => sum + (candidate.estimatedAnnualOutputKwh ?? 0),
    0,
  );
  const totalCost = solarCandidates.reduce(
    (sum, candidate) => sum + candidate.estimatedInstallationCostUsd,
    0,
  );
  const weightedScoreBase = solarCandidates.reduce(
    (sum, candidate) => sum + candidate.feasibilityScore * candidate.areaKm2,
    0,
  );
  const feasibilityScore =
    validAreaKm2 > 0 ? weightedScoreBase / validAreaKm2 : 0;
  const weatherSources = [
    ...new Set(
      solarCandidates
        .map((candidate) => candidate.metadata.weather_source)
        .filter(Boolean),
    ),
  ];
  const modelSources = [
    ...new Set(
      solarCandidates
        .map((candidate) => candidate.metadata.model_source)
        .filter(Boolean),
    ),
  ];

  return {
    type: "solar_siting",
    label: "Solar Siting",
    areaKm2: payload.area_m2 / 1_000_000,
    validAreaKm2,
    assetCount: panelCount,
    installedCapacityKw,
    annualMWh:
      estimatedAnnualOutputKwh > 0 ? estimatedAnnualOutputKwh / 1000 : null,
    totalCost,
    feasibilityScore,
    scoreExplanation:
      feasibilityScore >= 80
        ? "Strong fit. The selected site contains multiple buildable solar subregions after imagery and terrain screening."
        : feasibilityScore >= 60
          ? "Workable fit. Valid solar subregions were found, but build constraints still trim the usable footprint."
          : feasibilityScore > 0
            ? "Borderline fit. Some solar-capable subregions were found, but constraints remove a large share of the site."
            : "Weak fit. The site does not contain meaningful solar-ready subregions under the current screening settings.",
    suitable: solarCandidates.length > 0,
    suitabilityReason:
      solarCandidates.length > 0
        ? `Packed solar estimates are aggregated across ${solarCandidates.length} valid subregions after imagery, vector, and terrain screening.`
        : "No valid solar-ready subregions were found after imagery, vector, and terrain screening.",
    weatherSource:
      weatherSources.length > 0 ? weatherSources.join(", ") : "not-applicable",
    trendPeriodStart: null,
    trendPeriodEnd: null,
    dailyGeneration: [],
    metadata: {
      presetName: config.presetName,
      modelSource:
        modelSources.length > 0 ? modelSources.join(", ") : "not-applicable",
      imageryProvider: settings.imageryProvider,
      segmentationBackend: settings.segmentationBackend,
      terrainProvider: settings.terrainProvider,
      cellSizeMeters: settings.cellSizeMeters,
      solarCandidateCount: solarCandidates.length,
    },
    presetName: config.presetName,
    candidateCount: solarCandidates.length,
    candidates: solarCandidates,
    dataSources: payload.data_sources,
    notes: payload.pipeline_notes,
    imageryProvider: settings.imageryProvider,
    segmentationBackend: settings.segmentationBackend,
    terrainProvider: settings.terrainProvider,
    cellSizeMeters: settings.cellSizeMeters,
  };
};
