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
import { generateCandidateInsight } from "../lib/insightText";
import { formatUsd } from "../lib/financialProjection";

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
  const candidatesToRender = useMemo(() => {
    if (!result?.candidates) return [];
    return result.candidates;
  }, [result]);

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

        {(result?.type === "infrastructure" || result?.type === "solar_siting" || result?.type === "wind_siting" || result?.type === "data_center_siting") &&
          candidatesToRender.map((candidate) => {
            const colors = CANDIDATE_COLORS[candidate.useType];
            const isSelected = candidate.id === selectedCandidateId;
            const placementPolygons =
              candidate.placementPolygons?.length > 0
                ? candidate.placementPolygons
                : candidate.useType === "solar" && candidate.packingBlockPolygons?.length > 0
                  ? candidate.packingBlockPolygons
                  : [];
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
                        weight: isSelected ? 2.6 : 1.2,
                        fillColor: colors.fill,
                        fillOpacity:
                          candidate.useType === "data_center"
                            ? isSelected ? 0.26 : 0.12
                            : candidate.useType === "solar"
                              ? isSelected ? 0.30 : 0.22
                              : isSelected ? 0.18 : 0.08,
                        dashArray:
                          candidate.useType === "data_center" ? undefined : "5 6",
                      }}
                    />
                  ),
                )}
                {placementPolygons.map((polygon, polygonIndex) => (
                  <Polygon
                    key={`${candidate.id}-placement-${polygonIndex}`}
                    positions={polygon}
                    eventHandlers={{
                      click: () => onSelectCandidate(candidate.id),
                    }}
                    pathOptions={{
                      color:
                        candidate.useType === "solar"
                          ? colors.packingStroke
                          : colors.stroke,
                      weight: isSelected ? 1.8 : 1.2,
                      fillColor:
                        candidate.useType === "solar"
                          ? colors.packingFill
                          : colors.fill,
                      fillOpacity:
                        candidate.useType === "solar"
                          ? isSelected
                            ? 0.34
                            : 0.24
                          : isSelected
                            ? 0.28
                            : 0.18,
                    }}
                  />
                ))}
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
            autoPan
            offset={[0, -18]}
            eventHandlers={{ remove: () => onSetStatsVisible(false) }}
          >
            {(result.type === "infrastructure" || result.type === "solar_siting" || result.type === "wind_siting" || result.type === "data_center_siting") &&
            selectedCandidate ? (
              <div className="result-popup">
                <div className="popup-header-row">
                  <h3>{selectedCandidate.useLabel}</h3>
                  <span className={`popup-score-chip ${selectedCandidate.feasibilityScore >= 70 ? "good" : "caution"}`}>
                    {selectedCandidate.feasibilityScore.toFixed(0)}
                  </span>
                </div>
                <p className="popup-insight">{generateCandidateInsight(selectedCandidate)}</p>
                <div className="popup-metric-grid">
                  <div className="popup-metric">
                    <span>Area</span>
                    <strong>{(selectedCandidate.areaKm2 * 100).toFixed(1)} ha</strong>
                  </div>
                  <div className="popup-metric">
                    <span>Score</span>
                    <strong>{selectedCandidate.feasibilityScore.toFixed(1)}</strong>
                  </div>
                  {selectedCandidate.estimatedAnnualOutputKwh > 0 && (
                    <div className="popup-metric">
                      <span>Annual output</span>
                      <strong>{Math.round(selectedCandidate.estimatedAnnualOutputKwh / 1000).toLocaleString()} MWh</strong>
                    </div>
                  )}
                  {selectedCandidate.estimatedInstallationCostUsd > 0 && (
                    <div className="popup-metric">
                      <span>Est. cost</span>
                      <strong>{formatUsd(selectedCandidate.estimatedInstallationCostUsd)}</strong>
                    </div>
                  )}
                  {selectedCandidate.metadata?.panel_count > 0 && (
                    <div className="popup-metric">
                      <span>Panels</span>
                      <strong>{Math.round(selectedCandidate.metadata.panel_count).toLocaleString()}</strong>
                    </div>
                  )}
                  {selectedCandidate.metadata?.turbine_count > 0 && (
                    <div className="popup-metric">
                      <span>Turbines</span>
                      <strong>{selectedCandidate.metadata.turbine_count}</strong>
                    </div>
                  )}
                  {selectedCandidate.metadata?.installed_capacity_kw > 0 && (
                    <div className="popup-metric">
                      <span>Capacity</span>
                      <strong>
                        {selectedCandidate.metadata.installed_capacity_kw >= 1000
                          ? `${(selectedCandidate.metadata.installed_capacity_kw / 1000).toFixed(1)} MW`
                          : `${Math.round(selectedCandidate.metadata.installed_capacity_kw).toLocaleString()} kW`}
                      </strong>
                    </div>
                  )}
                </div>
                <p className="popup-reasoning">{selectedCandidate.reasoning?.[0]}</p>
                {result.dataSources && (
                  <p className="popup-sources">
                    Sources: {result.dataSources.imagery}, {result.dataSources.terrain}
                  </p>
                )}
              </div>
            ) : result.type === "infrastructure" || result.type === "solar_siting" || result.type === "wind_siting" || result.type === "data_center_siting" ? (
              <div className="result-popup">
                <h3>{result.label}</h3>
                <p>Area: {result.areaKm2.toFixed(2)} km²</p>
                {result.subdivisionsEvaluated ? (
                  <p>
                    Screened analysis tiles:{" "}
                    {result.subdivisionsEvaluated.toLocaleString()}
                  </p>
                ) : null}
                <p>
                  {result.type === "solar_siting"
                    ? "No valid solar-ready subregions cleared the current screening settings."
                    : result.type === "wind_siting"
                      ? "No valid wind-ready subregions cleared the current screening settings."
                      : result.type === "data_center_siting"
                        ? "No valid data center subregions cleared the current screening settings."
                        : "No buildable subregions cleared the current screening settings."}
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
