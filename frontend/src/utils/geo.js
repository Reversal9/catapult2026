export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export const normLng = (lng) => {
  let value = lng;
  while (value > 180) value -= 360;
  while (value < -180) value += 360;
  return value;
};

export const haversineMeters = (a, b) => {
  const radius = 6371000;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;
  return 2 * radius * Math.asin(Math.min(1, Math.sqrt(h)));
};

export const rectangleFromTwoPoints = (a, b) => {
  const south = Math.min(a.lat, b.lat);
  const north = Math.max(a.lat, b.lat);
  const west = Math.min(a.lng, b.lng);
  const east = Math.max(a.lng, b.lng);
  return [
    [south, west],
    [south, east],
    [north, east],
    [north, west],
  ];
};

export const centroid = (points) => {
  if (!points.length) return { lat: 0, lng: 0 };
  const lat = points.reduce((sum, p) => sum + p[0], 0) / points.length;
  const lng = points.reduce((sum, p) => sum + p[1], 0) / points.length;
  return { lat, lng };
};

export const polygonAreaKm2 = (points) => {
  if (points.length < 3) return 0;
  const c = centroid(points);
  const latScale = 111320;
  const lngScale = 111320 * Math.cos((c.lat * Math.PI) / 180);
  let twiceArea = 0;

  for (let i = 0; i < points.length; i += 1) {
    const j = (i + 1) % points.length;
    const x1 = points[i][1] * lngScale;
    const y1 = points[i][0] * latScale;
    const x2 = points[j][1] * lngScale;
    const y2 = points[j][0] * latScale;
    twiceArea += x1 * y2 - x2 * y1;
  }

  return Math.abs(twiceArea / 2) / 1_000_000;
};

export const regionAreaKm2 = (region) => {
  if (region.type === "circle") {
    const radiusKm = region.radiusMeters / 1000;
    return Math.PI * radiusKm * radiusKm;
  }
  return polygonAreaKm2(region.points);
};

export const regionCenter = (region) => {
  if (region.type === "circle") return region.center;
  return centroid(region.points);
};
