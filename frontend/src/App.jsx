/**
 * Catapult 2026 - Main Application Component
 *
 * This component serves as the primary orchestrator for the renewables analysis web application.
 *
 * Key Responsibilities:
 * 1. Map Management - Provides the Leaflet map interface for drawing regions
 * 2. State Management - Manages all application state (coordinates, draw mode, analysis results)
 * 3. Analysis Orchestration - Routes analysis requests to appropriate backend endpoints
 * 4. UI Integration - Coordinates between ControlPanel, MapScene, and result displays
 * 5. Theme Management - Handles light/dark theme switching
 *
 * Data Flow:
 * - User draws region on map → triggers applyPolygon()
 * - User selects analysis type (solar/asset/infrastructure)
 * - runAnalysis() calls backend API with region + parameters
 * - Results are mapped and displayed as overlays on map
 *
 * State Structure:
 * - Geographic: p1, p2, region (polygon coordinates and bounds)
 * - UI: theme, panelCollapsed, landingState, advancedOpen
 * - Analysis: energyType, selectedModel, solarSpec, windSpec, dataCenterSpec
 * - Results: result (analysis output), selectedCandidateId (for drilling down)
 * - Interaction: searching (loading state), submitError (validation errors)
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import "leaflet/dist/leaflet.css";
import "./App.css";
import { analyzeAssetRegion } from "./lib/assetAnalysisApi";
import ControlPanel from "./components/ControlPanel";
import LandingOverlay from "./components/LandingOverlay";
import MapScene from "./components/MapScene";
import TopBar from "./components/TopBar";
import TrendModal from "./components/TrendModal";
import { ASSET_PRESETS } from "./constants/models";
import { analyzeInfrastructureRegion } from "./lib/infrastructureAnalysisApi";
import { mapAssetResult } from "./lib/assetResult";
import {
  mapInfrastructureResult,
  mapSolarSitingResult,
} from "./lib/infrastructureResult";
import {
  clamp,
  haversineMeters,
  normLng,
  rectangleFromTwoPoints,
  regionCenter,
} from "./utils/geo";
import { formatDmsPair, parseDmsPair } from "./utils/dms";
import { defaultSpec, specFieldsFor } from "./utils/assetSpecs";

function App() {
  const mapRef = useRef(null);
  const popupRef = useRef(null);

  // === Theme and UI State ===
  const [theme, setTheme] = useState("light");
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [landingState, setLandingState] = useState("visible"); // visible → fading → hidden
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeCoordField, setActiveCoordField] = useState(null); // null or "p1" or "p2"
  const [userMovedMap, setUserMovedMap] = useState(false);

  // === Geographic State ===
  // Two reference points for bounding rectangle
  const [p1, setP1] = useState({ lat: 40.446, lng: -86.945 });
  const [p2, setP2] = useState({ lat: 40.425, lng: -86.865 });
  
  // Text representation of coordinates (for display and editing)
  const [p1Text, setP1Text] = useState(
    formatDmsPair({ lat: 40.446, lng: -86.945 }),
  );
  const [p2Text, setP2Text] = useState(
    formatDmsPair({ lat: 40.425, lng: -86.865 }),
  );
  
  // Error messages for coordinate validation
  const [p1Error, setP1Error] = useState("");
  const [p2Error, setP2Error] = useState("");

  // === Drawing State ===
  const [drawMode, setDrawMode] = useState("circle"); // rectangle, circle, polygon
  const [draftPoints, setDraftPoints] = useState([]); // Points being drafted for polygon
  const [region, setRegion] = useState({
    type: "polygon",
    points: rectangleFromTwoPoints(
      { lat: 40.446, lng: -86.945 },
      { lat: 40.425, lng: -86.865 },
    ),
    source: "rectangle",
  });

  // === Analysis Parameters ===
  const [energyType, setEnergyType] = useState("");
  const [modelMode, setModelMode] = useState("predefined");
  const [selectedModel, setSelectedModel] = useState("");
  const [imageryProvider, setImageryProvider] = useState("usgs");
  const [segmentationBackend, setSegmentationBackend] = useState("auto");
  const [terrainProvider, setTerrainProvider] = useState("opentopodata");
  const [cellSizeMeters, setCellSizeMeters] = useState(300);
  
  // Solar/wind/data-center specifications (for custom analysis)
  const [solarSpec, setSolarSpec] = useState(defaultSpec("solar"));
  const [windSpec, setWindSpec] = useState(defaultSpec("wind"));
  const [dataCenterSpec, setDataCenterSpec] = useState(
    defaultSpec("data_center"),
  );

  // === Results and Interaction State ===
  const [submitError, setSubmitError] = useState(""); // Validation errors
  const [searching, setSearching] = useState(false); // Loading indicator
  const [statsVisible, setStatsVisible] = useState(false);
  const [result, setResult] = useState(null); // Analysis result from backend
  const [selectedCandidateId, setSelectedCandidateId] = useState(null); // For drilling into specific site
  const [trendOpen, setTrendOpen] = useState(false);

  // === Landing Screen Animation ===
  /**
   * Triggers transition from landing screen to app.
   * Fades out overlay and enables interactions.
   */
  const enterApp = useCallback(() => {
    if (landingState !== "visible") return;
    setLandingState("fading");
    window.setTimeout(() => setLandingState("hidden"), 320);
  }, [landingState]);

  useEffect(() => {
    if (landingState === "hidden") return undefined;
    const onKey = () => enterApp();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enterApp, landingState]);

  /**
   * Apply a coordinate update to either p1 or p2.
   * Validates format and updates both decimal and text representations.
   */
  const applyCoord = (id, coord) => {
    const next = {
      lat: clamp(coord.lat, -89.999, 89.999),
      lng: normLng(coord.lng),
    };

    if (id === "p1") {
      setP1(next);
      setP1Text(formatDmsPair(next));
      setP1Error("");
    } else {
      setP2(next);
      setP2Text(formatDmsPair(next));
      setP2Error("");
    }

    setRegion({
      type: "polygon",
      points: rectangleFromTwoPoints(
        id === "p1" ? next : p1,
        id === "p2" ? next : p2,
      ),
      source: "rectangle",
    });
  };

  const onCoordChange = (id, value) => {
    if (id === "p1") setP1Text(value);
    else setP2Text(value);

    const parsed = parseDmsPair(value);
    if (!parsed.ok) {
      if (id === "p1") setP1Error(parsed.message);
      else setP2Error(parsed.message);
      return;
    }

    applyCoord(id, parsed.value);
  };

  const onMapClick = (latlng) => {
    if (landingState !== "hidden") enterApp();

    if (activeCoordField) {
      applyCoord(activeCoordField, latlng);
      setActiveCoordField(null);
      return;
    }

    if (!advancedOpen) return;

    if (drawMode === "circle") {
      setDraftPoints((current) => {
        const next = [...current, [latlng.lat, latlng.lng]];
        if (next.length === 2) {
          setRegion({
            type: "circle",
            center: { lat: next[0][0], lng: next[0][1] },
            radiusMeters: haversineMeters(
              { lat: next[0][0], lng: next[0][1] },
              { lat: next[1][0], lng: next[1][1] },
            ),
            source: "circle",
          });
          return [];
        }
        return next;
      });
      return;
    }

    if (drawMode === "polygon") {
      setDraftPoints((current) => [...current, [latlng.lat, latlng.lng]]);
    }
  };

  const finalizePolygon = () => {
    if (draftPoints.length < 3) {
      setSubmitError("Polygon needs at least three points.");
      return;
    }
    setRegion({ type: "polygon", points: draftPoints, source: "polygon" });
    setDraftPoints([]);
    setSubmitError("");
  };

  const removeLastPolygonPoint = () => {
    setDraftPoints((current) => current.slice(0, -1));
  };

  const useRectangleRegion = () => {
    setRegion({
      type: "polygon",
      points: rectangleFromTwoPoints(p1, p2),
      source: "rectangle",
    });
    setDraftPoints([]);
    setSubmitError("");
  };

  const mapBounds = useMemo(() => {
    if (region.type === "circle") {
      const c = region.center;
      const radiusKm = region.radiusMeters / 1000;
      const latDelta = radiusKm / 111.32;
      const lngDelta =
        radiusKm / (111.32 * Math.max(0.25, Math.cos((c.lat * Math.PI) / 180)));
      return [
        [c.lat - latDelta, c.lng - lngDelta],
        [c.lat + latDelta, c.lng + lngDelta],
      ];
    }

    return region.points;
  }, [region]);

  const fitRegion = useCallback(
    (duration = 0.6) => {
      const map = mapRef.current;
      if (!map) return;

      map.fitBounds(mapBounds, {
        padding: [56, 56],
        animate: true,
        duration,
      });
    },
    [mapBounds],
  );

  const assetPresets = useMemo(
    () =>
      energyType && energyType !== "infrastructure"
        ? (ASSET_PRESETS[energyType] ?? [])
        : [],
    [energyType],
  );
  const modelValue = modelMode === "predefined" ? selectedModel : "custom-spec";
  const requiresModel = energyType !== "infrastructure";
  const activeSpec =
    energyType === "solar"
      ? solarSpec
      : energyType === "wind"
        ? windSpec
        : dataCenterSpec;
  const assetSpecFields = useMemo(
    () =>
      energyType && energyType !== "infrastructure"
        ? specFieldsFor(energyType, activeSpec)
        : [],
    [activeSpec, energyType],
  );

  const isReady =
    !!energyType &&
    (!requiresModel || !!modelValue) &&
    !p1Error &&
    !p2Error &&
    !!region &&
    (region.type !== "circle" || region.radiusMeters > 1) &&
    (region.type !== "polygon" || region.points.length >= 3);

  const runAnalysis = async () => {
    const errors = [];
    if (p1Error || p2Error) errors.push("Fix coordinate formatting first.");
    if (!energyType) errors.push("Choose an asset type.");
    if (requiresModel && !modelValue) {
      errors.push("Choose a preset or enter a custom specification.");
    }
    if (!region) errors.push("Define a region on the map.");

    if (errors.length) {
      setSubmitError(errors.join(" "));
      return;
    }

    setSubmitError("");
    setSearching(true);
    fitRegion(0.55);

    try {
      if (energyType === "infrastructure") {
        const infrastructureResult = await analyzeInfrastructureRegion(region, {
          imagery_provider: imageryProvider,
          segmentation_backend: segmentationBackend,
          terrain_provider: terrainProvider,
          cell_size_m: cellSizeMeters,
          solar_spec: solarSpec,
          allowed_use_types: ["solar", "wind", "data_center"],
        });
        const mappedResult = mapInfrastructureResult(infrastructureResult, {
          imageryProvider,
          segmentationBackend,
          terrainProvider,
          cellSizeMeters,
        });
        setSelectedCandidateId(mappedResult.candidates[0]?.id ?? null);
        setResult(mappedResult);
        setTrendOpen(false);
      } else if (energyType === "solar") {
        const infrastructureResult = await analyzeInfrastructureRegion(region, {
          imagery_provider: imageryProvider,
          segmentation_backend: segmentationBackend,
          terrain_provider: terrainProvider,
          cell_size_m: cellSizeMeters,
          solar_spec: solarSpec,
          allowed_use_types: ["solar"],
        });
        const presetName =
          modelMode === "predefined"
            ? (assetPresets.find((preset) => preset.id === selectedModel)?.label ??
                null)
            : "Custom specification";
        const mappedResult = mapSolarSitingResult(
          infrastructureResult,
          {
            imageryProvider,
            segmentationBackend,
            terrainProvider,
            cellSizeMeters,
          },
          { presetName },
        );
        setSelectedCandidateId(mappedResult.candidates[0]?.id ?? null);
        setResult(mappedResult);
        setTrendOpen(false);
      } else {
        const assetResult = await analyzeAssetRegion(region, {
          assetType: energyType,
          presetName:
            modelMode === "predefined"
              ? (assetPresets.find((preset) => preset.id === selectedModel)
                  ?.label ?? null)
              : "Custom specification",
          solarSpec,
          windSpec,
          dataCenterSpec,
        });
        setSelectedCandidateId(null);
        setResult(
          mapAssetResult(assetResult, {
            presetName:
              modelMode === "predefined"
                ? (assetPresets.find((preset) => preset.id === selectedModel)
                    ?.label ?? null)
                : "Custom specification",
          }),
        );
        setTrendOpen(false);
      }

      setStatsVisible(true);
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : "The backend could not analyze this region.",
      );
    } finally {
      setSearching(false);
    }
  };

  const activeInfrastructureCandidate = useMemo(() => {
    if (!result?.candidates) return null;
    return (
      result.candidates.find(
        (candidate) => candidate.id === selectedCandidateId,
      ) ??
      result.candidates[0] ??
      null
    );
  }, [result, selectedCandidateId]);

  const popupPosition = useMemo(() => {
    if (activeInfrastructureCandidate) {
      return [
        activeInfrastructureCandidate.center.lat,
        activeInfrastructureCandidate.center.lng,
      ];
    }
    const c = regionCenter(region);
    return [c.lat, c.lng];
  }, [activeInfrastructureCandidate, region]);

  useEffect(() => {
    if (!mapRef.current) return;
    if (searching || statsVisible || userMovedMap) return;
    fitRegion(0);
  }, [fitRegion, searching, statsVisible, userMovedMap]);

  return (
    <main className={`app-root theme-${theme}`}>
      <MapScene
        region={region}
        draftPoints={draftPoints}
        p1={p1}
        p2={p2}
        result={result}
        selectedCandidateId={selectedCandidateId}
        selectedCandidate={activeInfrastructureCandidate}
        statsVisible={statsVisible}
        popupRef={popupRef}
        popupPosition={popupPosition}
        onMapClick={onMapClick}
        onMapMove={() => setUserMovedMap(true)}
        onToggleStats={() => setStatsVisible((value) => !value)}
        onSetStatsVisible={setStatsVisible}
        onApplyCoord={applyCoord}
        onSelectCandidate={(candidateId) => {
          setSelectedCandidateId(candidateId);
          setStatsVisible(true);
        }}
        onMapReady={(event) => {
          mapRef.current = event.target;
          fitRegion(0);
        }}
        onLandingInteraction={enterApp}
        landingHidden={landingState === "hidden"}
        theme={theme}
      />

      <div className="ui-layer">
        <TopBar
          theme={theme}
          expanded={settingsOpen}
          onToggleExpanded={() => setSettingsOpen((value) => !value)}
          onToggleTheme={() =>
            setTheme((value) => (value === "light" ? "dark" : "light"))
          }
          userMovedMap={userMovedMap}
          onRefocus={() => {
            fitRegion(0.55);
            setUserMovedMap(false);
          }}
        />

        <ControlPanel
          collapsed={panelCollapsed}
          onToggleCollapsed={() => setPanelCollapsed((value) => !value)}
          p1Text={p1Text}
          p2Text={p2Text}
          p1Error={p1Error}
          p2Error={p2Error}
          onCoordChange={onCoordChange}
          onCoordFocus={setActiveCoordField}
          advancedOpen={advancedOpen}
          onToggleAdvanced={() => setAdvancedOpen((value) => !value)}
          drawMode={drawMode}
          onDrawModeChange={(mode) => {
            setDrawMode(mode);
            setDraftPoints([]);
          }}
          onFinalizePolygon={finalizePolygon}
          onRemoveLastPoint={removeLastPolygonPoint}
          onUseRectangle={useRectangleRegion}
          hasDraftPoints={draftPoints.length > 0}
          energyType={energyType}
          modelMode={modelMode}
          selectedModel={selectedModel}
          assetSpecFields={assetSpecFields}
          assetPresets={assetPresets}
          imageryProvider={imageryProvider}
          segmentationBackend={segmentationBackend}
          terrainProvider={terrainProvider}
          cellSizeMeters={cellSizeMeters}
          onEnergyTypeChange={(nextType) => {
            setEnergyType(nextType);
            setSelectedModel(ASSET_PRESETS[nextType]?.[0]?.id ?? "");
            if (nextType !== "infrastructure") {
              setModelMode("predefined");
            }
            setSelectedCandidateId(null);
            setResult(null);
            setStatsVisible(false);
            setSubmitError("");
          }}
          onModelModeChange={setModelMode}
          onSelectedModelChange={(presetId) => {
            setSelectedModel(presetId);
            const preset = assetPresets.find((item) => item.id === presetId);
            if (!preset) return;
            if (energyType === "solar")
              setSolarSpec(structuredClone(preset.spec));
            else if (energyType === "wind")
              setWindSpec(structuredClone(preset.spec));
            else if (energyType === "data_center") {
              setDataCenterSpec(structuredClone(preset.spec));
            }
          }}
          onAssetSpecChange={(key, value) => {
            const numeric = Number(value);
            if (Number.isNaN(numeric)) return;
            if (energyType === "solar") {
              setSolarSpec((current) => ({ ...current, [key]: numeric }));
            } else if (energyType === "wind") {
              setWindSpec((current) => ({ ...current, [key]: numeric }));
            } else if (energyType === "data_center") {
              setDataCenterSpec((current) => ({ ...current, [key]: numeric }));
            }
          }}
          onImageryProviderChange={setImageryProvider}
          onSegmentationBackendChange={setSegmentationBackend}
          onTerrainProviderChange={setTerrainProvider}
          onCellSizeMetersChange={(value) => {
            const numeric = Number(value);
            if (Number.isNaN(numeric)) {
              setCellSizeMeters(300);
              return;
            }
            setCellSizeMeters(clamp(Math.round(numeric), 100, 2000));
          }}
          submitError={submitError}
          isReady={isReady}
          searching={searching}
          result={result}
          selectedCandidateId={selectedCandidateId}
          onSelectCandidate={(candidateId) => {
            setSelectedCandidateId(candidateId);
            setStatsVisible(true);
          }}
          onRunAnalysis={runAnalysis}
          onOpenTrend={() => setTrendOpen(true)}
        />

        <TrendModal
          open={trendOpen}
          onClose={() => setTrendOpen(false)}
          result={result?.type !== "infrastructure" ? result : null}
        />
      </div>

      <LandingOverlay landingState={landingState} onEnter={enterApp} />
    </main>
  );
}

export default App;
