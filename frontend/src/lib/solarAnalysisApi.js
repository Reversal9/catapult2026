import DEFAULT_BACKEND_URL, {
  readErrorDetail,
  regionToPolygonPoints,
} from "./analysisApiShared";

export const buildSolarRequest = (region, overrides = {}) => ({
  points: regionToPolygonPoints(region),
  ...overrides,
});

export const analyzeSolarRegion = async (region, overrides = {}) => {
  const response = await fetch(`${DEFAULT_BACKEND_URL}/solar/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(buildSolarRequest(region, overrides)),
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Solar analysis request failed."));
  }

  return response.json();
};
