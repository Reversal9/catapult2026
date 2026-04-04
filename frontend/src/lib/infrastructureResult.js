import { regionCenter } from "../utils/geo";

export const titleCaseUseType = (value) =>
  value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

export const mapInfrastructureResult = (payload, settings) => {
  const candidates = payload.candidates.map((candidate) => {
    const polygon = candidate.polygon.map((point) => [point.lat, point.lon]);
    return {
      id: candidate.id,
      useType: candidate.use_type,
      useLabel: titleCaseUseType(candidate.use_type),
      polygon,
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
