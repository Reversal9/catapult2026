import DEFAULT_BACKEND_URL, {
  readErrorDetail,
  regionToPolygonPoints,
} from "./analysisApiShared";

export const buildAssetAnalysisRequest = (region, options) => ({
  asset_type: options.assetType,
  preset_name: options.presetName ?? null,
  points: regionToPolygonPoints(region),
  solar_spec: options.solarSpec,
  wind_spec: options.windSpec,
  data_center_spec: options.dataCenterSpec,
});

export const analyzeAssetRegion = async (region, options) => {
  const response = await fetch(`${DEFAULT_BACKEND_URL}/asset/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildAssetAnalysisRequest(region, options)),
  });

  if (!response.ok) {
    throw new Error(
      await readErrorDetail(response, "Asset analysis request failed."),
    );
  }

  return response.json();
};
