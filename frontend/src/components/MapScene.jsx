import React, { useMemo, useState } from "react";
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
import { rectangleFromTwoPoints } from "../utils/geo";

const CANDIDATE_COLORS = {
  solar: {
    stroke: "#b42318",
    fill: "#ef4444",
    packingStroke: "#7f1d1d",
    packingFill: "#dc2626",
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
  const [dragPreview, setDragPreview] = useState(null);

  const previewP1 = dragPreview?.p1 ?? p1;
  const previewP2 = dragPreview?.p2 ?? p2;
  const displayedRegion = useMemo(() => {
    if (!dragPreview) {
      return region;
    }

    return {
      type: "polygon",
      points: rectangleFromTwoPoints(previewP1, previewP2),
      source: "rectangle",
    };
  }, [dragPreview, previewP1, previewP2, region]);

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
          center={[40.4259, -86.9081]}
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

        {displayedRegion.type === "circle" ? (
          <Circle
            center={[displayedRegion.center.lat, displayedRegion.center.lng]}
            radius={displayedRegion.radiusMeters}
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
            positions={displayedRegion.points}
            eventHandlers={{ click: () => result && onToggleStats() }}
            pathOptions={{
              color: "#1b7d67",
              weight: 2,
              fillColor: "#65c9ad",
              fillOpacity: 0.14,
            }}
          />
        )}

        {(result?.type === "infrastructure" || result?.type === "solar_siting") &&
          result.candidates.map((candidate) => {
            const colors = CANDIDATE_COLORS[candidate.useType];
            const isSelected = candidate.id === selectedCandidateId;
            return (
              <React.Fragment key={candidate.id}>
                {(candidate.validRegionPolygons ?? [candidate.polygon]).map(
                  (polygon, polygonIndex) => (
                    <Polygon
                      key={`${candidate.id}-valid-${polygonIndex}`}
                      positions={polygon}
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
                  ),
                )}
                {candidate.useType === "solar" &&
                  (candidate.packingBlockPolygons ?? []).map(
                    (polygon, polygonIndex) => (
                      <Polygon
                        key={`${candidate.id}-packing-${polygonIndex}`}
                        positions={polygon}
                        eventHandlers={{
                          click: () => onSelectCandidate(candidate.id),
                        }}
                        pathOptions={{
                          color: colors.packingStroke,
                          weight: isSelected ? 1.6 : 1.1,
                          fillColor: colors.packingFill,
                          fillOpacity: isSelected ? 0.36 : 0.22,
                        }}
                      />
                    ),
                  )}
              </React.Fragment>
            );
          })}

        {draftPoints.length > 0 && (
          <Polyline
            positions={draftPoints}
            pathOptions={{ color: "#b17d2f", weight: 2, dashArray: "5 7" }}
          />
        )}

        <Marker
          position={[previewP1.lat, previewP1.lng]}
          icon={markerIcon("#4ab394")}
          draggable
          eventHandlers={{
            dragstart: () => {
              setDragPreview({ p1, p2 });
            },
            drag: (event) =>
              setDragPreview((current) => ({
                p1: event.target.getLatLng(),
                p2: current?.p2 ?? p2,
              })),
            dragend: (event) => {
              setDragPreview(null);
              onApplyCoord("p1", event.target.getLatLng());
            },
            click: onLandingInteraction,
          }}
        />
        <Marker
          position={[previewP2.lat, previewP2.lng]}
          icon={markerIcon("#c09244")}
          draggable
          eventHandlers={{
            dragstart: () => {
              setDragPreview({ p1, p2 });
            },
            drag: (event) =>
              setDragPreview((current) => ({
                p1: current?.p1 ?? p1,
                p2: event.target.getLatLng(),
              })),
            dragend: (event) => {
              setDragPreview(null);
              onApplyCoord("p2", event.target.getLatLng());
            },
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
            {(result.type === "infrastructure" || result.type === "solar_siting") &&
            selectedCandidate ? (
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
                {selectedCandidate.metadata?.panel_count ? (
                  <p>
                    Packed panels:{" "}
                    {selectedCandidate.metadata.panel_count.toLocaleString()}
                  </p>
                ) : null}
                {selectedCandidate.metadata?.installed_capacity_kw ? (
                  <p>
                    Installed capacity:{" "}
                    {selectedCandidate.metadata.installed_capacity_kw.toLocaleString()}{" "}
                    kW
                  </p>
                ) : null}
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
                {selectedCandidate.reasoning[2] ? (
                  <p>{selectedCandidate.reasoning[2]}</p>
                ) : null}
                <p>
                  Sources: {result.dataSources.imagery},{" "}
                  {result.dataSources.vector_data},{" "}
                  {result.dataSources.segmentation},{" "}
                  {result.dataSources.terrain}
                </p>
              </div>
            ) : result.type === "infrastructure" || result.type === "solar_siting" ? (
              <div className="result-popup">
                <h3>{result.label}</h3>
                <p>Area: {result.areaKm2.toFixed(2)} km²</p>
                {result.subdivisionsEvaluated ? (
                  <p>
                    Evaluated cells:{" "}
                    {result.subdivisionsEvaluated.toLocaleString()}
                  </p>
                ) : null}
                <p>
                  {result.type === "solar_siting"
                    ? "No valid solar-ready subregions cleared the current screening settings."
                    : "No candidate cells cleared the current feasibility thresholds."}
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
