import DEFAULT_BACKEND_URL, {
  readErrorDetail,
  regionToPolygonPoints,
} from "./analysisApiShared";

export const buildInfrastructureRequest = (region, overrides = {}) => ({
  points: regionToPolygonPoints(region),
  cell_size_m: overrides.cell_size_m ?? 300,
  imagery_provider: overrides.imagery_provider ?? "usgs",
  segmentation_backend: overrides.segmentation_backend ?? "auto",
  terrain_provider: overrides.terrain_provider ?? "opentopodata",
  include_debug_layers: overrides.include_debug_layers ?? false,
  solar_spec: overrides.solar_spec,
  wind_spec: overrides.wind_spec,
  data_center_spec: overrides.data_center_spec,
  allowed_use_types: overrides.allowed_use_types,
});

export const analyzeInfrastructureRegion = async (region, overrides = {}) => {
  const response = await fetch(
    `${DEFAULT_BACKEND_URL}/infrastructure/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildInfrastructureRequest(region, overrides)),
    },
  );

  if (!response.ok) {
    throw new Error(
      await readErrorDetail(
        response,
        "Infrastructure analysis request failed.",
      ),
    );
  }

  return response.json();
};
