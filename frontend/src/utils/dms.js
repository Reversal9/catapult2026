const DMS_RE =
  /^\s*(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)"?\s*([NnSs])\s+(\d{1,3})[°\s]+(\d{1,2})['\s]+(\d{1,2}(?:\.\d+)?)"?\s*([EeWw])\s*$/;

const toDmsPart = (raw, isLat) => {
  const value = Math.abs(raw);
  const deg = Math.floor(value);
  const minsFull = (value - deg) * 60;
  const min = Math.floor(minsFull);
  const sec = (minsFull - min) * 60;
  const hemi = isLat ? (raw >= 0 ? "N" : "S") : raw >= 0 ? "E" : "W";
  return `${deg}°${String(min).padStart(2, "0")}'${sec.toFixed(1)}"${hemi}`;
};

export const formatDmsPair = ({ lat, lng }) =>
  `${toDmsPart(lat, true)} ${toDmsPart(lng, false)}`;

export const parseDmsPair = (value) => {
  const match = value.match(DMS_RE);
  if (!match) {
    return {
      ok: false,
      message: "Use DMS format: 43°43'25.7\"N 80°11'38.5\"W",
    };
  }

  const latDeg = Number(match[1]);
  const latMin = Number(match[2]);
  const latSec = Number(match[3]);
  const latHem = match[4].toUpperCase();
  const lngDeg = Number(match[5]);
  const lngMin = Number(match[6]);
  const lngSec = Number(match[7]);
  const lngHem = match[8].toUpperCase();

  if (
    latDeg > 90 ||
    lngDeg > 180 ||
    latMin >= 60 ||
    lngMin >= 60 ||
    latSec >= 60 ||
    lngSec >= 60
  ) {
    return {
      ok: false,
      message: "Latitude/longitude values are out of range.",
    };
  }

  let lat = latDeg + latMin / 60 + latSec / 3600;
  let lng = lngDeg + lngMin / 60 + lngSec / 3600;
  if (latHem === "S") lat *= -1;
  if (lngHem === "W") lng *= -1;

  return { ok: true, value: { lat, lng } };
};
