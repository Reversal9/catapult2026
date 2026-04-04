import React from "react";
import {
  Circle,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
} from "react-leaflet";
import MapEvents from "./MapEvents";
import { markerIcon } from "../map/icons";

const CANDIDATE_COLORS = {
  solar: {
    stroke: "#cc7a1b",
    fill: "#f4c86b",
  },
  wind: {
    stroke: "#2d83b7",
    fill: "#85d3ff",
  },
  data_center: {
    stroke: "#7c5bd6",
    fill: "#c6b1ff",
  },
};

function MapScene({
  region,
  draftPoints,
  p1,
  p2,
  result,
  selectedCandidateId,
  selectedCandidate,
  statsVisible,
  popupRef,
  popupPosition,
  onMapClick,
  onMapMove,
  onToggleStats,
  onSetStatsVisible,
  onApplyCoord,
  onSelectCandidate,
  onMapReady,
  onLandingInteraction,
  landingHidden,
  theme,
}) {
  const tilesUrl =
    theme === "light"
      ? "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  const tileAttribution =
    theme === "light"
      ? "&copy; OpenStreetMap contributors"
      : "&copy; OpenStreetMap contributors &copy; CARTO";

  return (
    <div className="map-layer" aria-hidden={!landingHidden}>
      <MapContainer
        className="map-canvas"
        center={[43.67, -80.13]}
        zoom={10}
        zoomControl
        scrollWheelZoom
        whenReady={onMapReady}
      >
        <TileLayer
          url={tilesUrl}
          attribution={tileAttribution}
          maxZoom={20}
          subdomains={["a", "b", "c"]}
        />
        <MapEvents onMapClick={onMapClick} onMapMove={onMapMove} />

        {region.type === "circle" ? (
          <Circle
            center={[region.center.lat, region.center.lng]}
            radius={region.radiusMeters}
            eventHandlers={{ click: () => result && onToggleStats() }}
            pathOptions={{
              color: "#1b7d67",
              weight: 2,
              fillColor: "#65c9ad",
              fillOpacity: 0.16,
            }}
          />
        ) : (
          <Polygon
            positions={region.points}
            eventHandlers={{ click: () => result && onToggleStats() }}
            pathOptions={{
              color: "#1b7d67",
              weight: 2,
              fillColor: "#65c9ad",
              fillOpacity: 0.14,
            }}
          />
        )}

        {result?.type === "infrastructure" &&
          result.candidates.map((candidate) => {
            const colors = CANDIDATE_COLORS[candidate.useType];
            const isSelected = candidate.id === selectedCandidateId;
            return (
              <Polygon
                key={candidate.id}
                positions={candidate.polygon}
                eventHandlers={{
                  click: () => onSelectCandidate(candidate.id),
                }}
                pathOptions={{
                  color: colors.stroke,
                  weight: isSelected ? 3 : 1.6,
                  fillColor: colors.fill,
                  fillOpacity: isSelected
                    ? 0.34
                    : 0.1 + Math.min(candidate.feasibilityScore / 100, 0.22),
                }}
              />
            );
          })}

        {draftPoints.length > 0 && (
          <Polyline
            positions={draftPoints}
            pathOptions={{ color: "#b17d2f", weight: 2, dashArray: "5 7" }}
          />
        )}

        <Marker
          position={[p1.lat, p1.lng]}
          icon={markerIcon("#4ab394")}
          draggable
          eventHandlers={{
            drag: (event) => onApplyCoord("p1", event.target.getLatLng()),
            dragend: (event) => onApplyCoord("p1", event.target.getLatLng()),
            click: onLandingInteraction,
          }}
        />
        <Marker
          position={[p2.lat, p2.lng]}
          icon={markerIcon("#c09244")}
          draggable
          eventHandlers={{
            drag: (event) => onApplyCoord("p2", event.target.getLatLng()),
            dragend: (event) => onApplyCoord("p2", event.target.getLatLng()),
            click: onLandingInteraction,
          }}
        />

        {statsVisible && result && (
          <Popup
            ref={popupRef}
            position={popupPosition}
            closeButton
            autoClose={false}
            closeOnClick={false}
            eventHandlers={{ remove: () => onSetStatsVisible(false) }}
          >
            {result.type === "infrastructure" && selectedCandidate ? (
              <div className="result-popup">
                <h3>{selectedCandidate.useLabel} Candidate</h3>
                <p>
                  Feasibility score:{" "}
                  {selectedCandidate.feasibilityScore.toFixed(1)}
                </p>
                <p>
                  Footprint: {(selectedCandidate.areaKm2 * 100).toFixed(2)} ha
                </p>
                <p>
                  Estimated cost: $
                  {selectedCandidate.estimatedInstallationCostUsd.toLocaleString()}
                </p>
                {selectedCandidate.estimatedAnnualOutputKwh && (
                  <p>
                    Estimated output:{" "}
                    {(
                      selectedCandidate.estimatedAnnualOutputKwh / 1000
                    ).toLocaleString()}{" "}
                    MWh/year
                  </p>
                )}
                <p>{selectedCandidate.reasoning[0]}</p>
                <p>{selectedCandidate.reasoning[1]}</p>
                <p>
                  Sources: {result.dataSources.imagery},{" "}
                  {result.dataSources.vector_data},{" "}
                  {result.dataSources.segmentation},{" "}
                  {result.dataSources.terrain}
                </p>
              </div>
            ) : result.type === "infrastructure" ? (
              <div className="result-popup">
                <h3>{result.label}</h3>
                <p>Area: {result.areaKm2.toFixed(2)} km²</p>
                <p>
                  Evaluated cells:{" "}
                  {result.subdivisionsEvaluated.toLocaleString()}
                </p>
                <p>
                  No candidate cells cleared the current feasibility thresholds.
                </p>
                <p>
                  Sources: {result.dataSources.imagery},{" "}
                  {result.dataSources.vector_data},{" "}
                  {result.dataSources.segmentation},{" "}
                  {result.dataSources.terrain}
                </p>
              </div>
            ) : (
              <div className="result-popup">
                <h3>{result.label} Summary</h3>
                <p>Area: {result.areaKm2.toFixed(2)} km²</p>
                {result.assetCount !== null &&
                  result.assetCount !== undefined && (
                    <p>Estimated units: {result.assetCount.toLocaleString()}</p>
                  )}
                {result.installedCapacityKw && (
                  <>
                    <p>
                      Installed capacity:{" "}
                      {result.installedCapacityKw.toLocaleString()} kW
                    </p>
                  </>
                )}
                {result.annualMWh && (
                  <p>
                    Estimated annual generation:{" "}
                    {result.annualMWh.toLocaleString()} MWh
                  </p>
                )}
                <p>Total cost: ${result.totalCost.toLocaleString()}</p>
                <p>Feasibility score: {result.feasibilityScore.toFixed(1)}</p>
                <p>{result.scoreExplanation}</p>
                <p>{result.suitabilityReason}</p>
                <p>
                  Weather source:{" "}
                  {result.weatherSource === "not-applicable"
                    ? "Not applicable"
                    : result.weatherSource}
                </p>
              </div>
            )}
          </Popup>
        )}
      </MapContainer>
    </div>
  );
}

export default MapScene;
