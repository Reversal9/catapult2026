 const DEFAULT_BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000";

const CIRCLE_SEGMENTS = 24;

const approximateCirclePoints = (
  center,
  radiusMeters,
  segments = CIRCLE_SEGMENTS,
) => {
  const latitudeRadius = radiusMeters / 111_320;
  const longitudeRadius =
    radiusMeters /
    (111_320 * Math.max(0.25, Math.cos((center.lat * Math.PI) / 180)));

  return Array.from({ length: segments }, (_, index) => {
    const angle = (2 * Math.PI * index) / segments;
    return {
      lat: center.lat + latitudeRadius * Math.sin(angle),
      lon: center.lng + longitudeRadius * Math.cos(angle),
    };
  });
};

const regionToPolygonPoints = (region) => {
  if (region.type === "circle") {
    return approximateCirclePoints(region.center, region.radiusMeters);
  }

  return region.points.map(([lat, lng]) => ({ lat, lon: lng }));
};

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
    const detail = await response.text();
    throw new Error(detail || "Solar analysis request failed.");
  }

  return response.json();
};