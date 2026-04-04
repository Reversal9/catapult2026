import L from "leaflet";

export const markerIcon = (color) =>
  L.divIcon({
    className: "map-pin-icon",
    html: `<span style="--pin:${color}"></span>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
