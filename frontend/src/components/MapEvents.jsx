import { useMapEvents } from "react-leaflet";

function MapEvents({ onMapClick, onMapMove }) {
  useMapEvents({
    click: (event) => onMapClick(event.latlng),
    movestart: onMapMove,
    zoomstart: onMapMove,
  });

  return null;
}

export default MapEvents;
