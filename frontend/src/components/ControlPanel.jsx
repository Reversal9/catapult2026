import React, { useState } from "react";
import {
  INFRASTRUCTURE_IMAGERY_PROVIDERS,
  INFRASTRUCTURE_SEGMENTATION_OPTIONS,
} from "../constants/infrastructureOptions";

function HelpButton({ label, help }) {
  const [open, setOpen] = useState(false);

  return (
    <span className={`help-wrap ${open ? "open" : ""}`}>
      <span className="label-with-help">
      <span>{label}</span>
      <button
        type="button"
        className="help-button"
        aria-label={`Help for ${label}`}
        aria-expanded={open}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        ?
      </button>
      </span>
      {open && (
        <span className="help-popover" role="note">
          {help}
        </span>
      )}
    </span>
  );
}

function ControlPanel({
  collapsed,
  onToggleCollapsed,
  p1Text,
  p2Text,
  p1Error,
  p2Error,
  onCoordChange,
  onCoordFocus,
  advancedOpen,
  onToggleAdvanced,
  drawMode,
  onDrawModeChange,
  onFinalizePolygon,
  onRemoveLastPoint,
  onUseRectangle,
  hasDraftPoints,
  energyType,
  modelMode,
  selectedModel,
  assetSpecFields,
  assetPresets,
  imageryProvider,
  segmentationBackend,
  cellSizeMeters,
  onEnergyTypeChange,
  onModelModeChange,
  onSelectedModelChange,
  onAssetSpecChange,
  onImageryProviderChange,
  onSegmentationBackendChange,
  onCellSizeMetersChange,
  submitError,
  isReady,
  searching,
  result,
  selectedCandidateId,
  onSelectCandidate,
  onRunAnalysis,
  onOpenTrend,
}) {
  const topCandidates =
    result?.type === "infrastructure" ? result.candidates.slice(0, 6) : [];

  return (
    <section className={`bottom-panel ${collapsed ? "collapsed" : ""}`} aria-label="Inputs">
      <div className="panel-header">
        <div>
          <h2>Planning Panel</h2>
          <p>
            {collapsed
              ? "Expand the panel to edit your region, asset settings, and results."
              : "Pick an asset, review the assumptions, and run the backend analysis."}
          </p>
        </div>
        <button
          type="button"
          className="icon-button"
          aria-label={collapsed ? "Expand panel" : "Collapse panel"}
          onClick={onToggleCollapsed}
        >
          {collapsed ? "▴" : "▾"}
        </button>
      </div>

      {!collapsed && (
        <>
          <div className="coords-row">
            <label>
              <HelpButton
                label="Point 1"
                help="First corner of the quick rectangle. You can type coordinates or click the map after selecting the field."
              />
              <input
                value={p1Text}
                onChange={(event) => onCoordChange("p1", event.target.value)}
                onFocus={() => onCoordFocus("p1")}
                placeholder={"43°43'25.7\"N 80°11'38.5\"W"}
              />
              {p1Error && <small className="field-error">{p1Error}</small>}
            </label>

            <label>
              <HelpButton
                label="Point 2"
                help="Second corner of the quick rectangle. Together with Point 1, this defines the default selection box."
              />
              <input
                value={p2Text}
                onChange={(event) => onCoordChange("p2", event.target.value)}
                onFocus={() => onCoordFocus("p2")}
                placeholder={"43°43'25.7\"N 80°11'38.5\"W"}
              />
              {p2Error && <small className="field-error">{p2Error}</small>}
            </label>
          </div>

          <div className="advanced-block">
            <button
              type="button"
              className={advancedOpen ? "expanded" : ""}
              onClick={onToggleAdvanced}
            >
              Advanced settings
            </button>

            <div className={`advanced-menu ${advancedOpen ? "open" : ""}`}>
              <div className="mode-row">
                <button
                  type="button"
                  className={drawMode === "circle" ? "active" : ""}
                  onClick={() => onDrawModeChange("circle")}
                >
                  Circle tool
                </button>
                <button
                  type="button"
                  className={drawMode === "polygon" ? "active" : ""}
                  onClick={() => onDrawModeChange("polygon")}
                >
                  Polygon tool
                </button>
                <button type="button" onClick={onFinalizePolygon}>
                  Close polygon
                </button>
                <button type="button" onClick={onRemoveLastPoint} disabled={!hasDraftPoints}>
                  Undo point
                </button>
                <button type="button" onClick={onUseRectangle}>
                  Use rectangle
                </button>
              </div>
              <p className="helper">
                Use this section to switch between rectangle, circle, and polygon region
                selection. Click a coordinate field and then the map to fill it.
              </p>
            </div>
          </div>

          <div className="energy-row">
            <label>
              <HelpButton
                label="Asset type"
                help="Pick one asset if you want one direct estimate. Pick the comparison option if you want the backend to rank the best subregions for solar, wind, and data centers."
              />
              <select value={energyType} onChange={(event) => onEnergyTypeChange(event.target.value)}>
                <option value="">Select asset</option>
                <option value="solar">Solar panels</option>
                <option value="wind">Wind turbines</option>
                <option value="data_center">Data center</option>
                <option value="infrastructure">Compare all three across the site</option>
              </select>
            </label>

            {energyType && energyType !== "infrastructure" && (
              <label>
                <HelpButton
                  label="Specification source"
                  help="Use a preset for a fast starting point, or custom if you already know the equipment values you want to test."
                />
                <select value={modelMode} onChange={(event) => onModelModeChange(event.target.value)}>
                  <option value="predefined">Use a preset</option>
                  <option value="custom">Enter custom specs</option>
                </select>
              </label>
            )}

            {energyType && energyType !== "infrastructure" && modelMode === "predefined" && (
              <label>
                <HelpButton
                  label="Preset"
                  help="A preset fills in example equipment values so you can compare ideas without typing every input yourself."
                />
                <select
                  value={selectedModel}
                  onChange={(event) => onSelectedModelChange(event.target.value)}
                >
                  <option value="">Select preset</option>
                  {assetPresets.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {energyType === "infrastructure" && (
              <label>
                <HelpButton
                  label="Imagery provider"
                  help="USGS is the free default choice. Other providers can be used only if the backend has their credentials."
                />
                <select
                  value={imageryProvider}
                  onChange={(event) => onImageryProviderChange(event.target.value)}
                >
                  {INFRASTRUCTURE_IMAGERY_PROVIDERS.map((provider) => (
                    <option key={provider.value} value={provider.value}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {energyType === "infrastructure" && (
              <label>
                <HelpButton
                  label="Segmentation"
                  help="This decides how the backend detects useful surfaces such as rooftops, open land, vegetation, and water."
                />
                <select
                  value={segmentationBackend}
                  onChange={(event) => onSegmentationBackendChange(event.target.value)}
                >
                  {INFRASTRUCTURE_SEGMENTATION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          {energyType && energyType !== "infrastructure" && modelMode === "custom" && (
            <div className="spec-grid">
              {assetSpecFields.map((field) => (
                <label key={field.key}>
                  <HelpButton label={field.label} help={field.help} />
                  <input
                    type="number"
                    min={field.min}
                    step={field.step ?? "any"}
                    value={field.value}
                    onChange={(event) => onAssetSpecChange(field.key, event.target.value)}
                  />
                </label>
              ))}
            </div>
          )}

          {energyType === "infrastructure" && (
            <div className="spec-grid single-row">
              <label>
                <HelpButton
                  label="Cell size (m)"
                  help="This is the width of each scored subregion. Smaller cells give finer detail. Larger cells run faster."
                />
                <input
                  type="number"
                  min="100"
                  max="2000"
                  step="50"
                  value={cellSizeMeters}
                  onChange={(event) => onCellSizeMetersChange(event.target.value)}
                />
                <small>Smaller cells give more detail but take longer to score.</small>
              </label>
            </div>
          )}

          {submitError && <p className="submit-error">{submitError}</p>}

          <div className="actions-row">
            <button
              type="button"
              className="primary"
              disabled={!isReady || searching}
              onClick={onRunAnalysis}
            >
              {searching ? "Computing..." : "Run analysis"}
            </button>
          </div>

          {result?.type === "infrastructure" && (
            <section className="candidate-results" aria-label="Infrastructure candidates">
              <div className="candidate-summary">
                <div>
                  <strong>{result.candidateCount}</strong> ranked candidates across{" "}
                  <strong>{result.subdivisionsEvaluated}</strong> evaluated cells
                </div>
                <div>
                  A higher feasibility score means the site clears more of the basic
                  screeners for the chosen use type.
                </div>
                <div>
                  Sources: {result.dataSources.imagery}, {result.dataSources.vector_data},{" "}
                  {result.dataSources.segmentation}, {result.dataSources.terrain}
                </div>
              </div>

              <div className="candidate-strip">
                {topCandidates.map((candidate) => (
                  <button
                    key={candidate.id}
                    type="button"
                    className={selectedCandidateId === candidate.id ? "candidate-pill active" : "candidate-pill"}
                    onClick={() => onSelectCandidate(candidate.id)}
                  >
                    <span>{candidate.useLabel}</span>
                    <strong>{candidate.feasibilityScore.toFixed(1)}</strong>
                  </button>
                ))}
              </div>
            </section>
          )}

          {result && result.type !== "infrastructure" && (
            <section className="asset-result-card" aria-label="Asset analysis result">
              <div className="asset-result-header">
                <div>
                  <h3>{result.label} Summary</h3>
                  <p>{result.scoreExplanation}</p>
                </div>
                <div className={`score-badge ${result.suitable ? "good" : "caution"}`}>
                  <span>Score {result.feasibilityScore.toFixed(1)}</span>
                  <HelpButton
                    label="Feasibility score"
                    help="This score is a simple fit check from 0 to 100. Higher means the site better matches the main needs for this asset, such as space, weather, and build practicality."
                  />
                </div>
              </div>

              <div className="asset-metrics">
                <p>Selected area: {result.areaKm2.toFixed(2)} km²</p>
                {result.assetCount !== null && result.assetCount !== undefined && (
                  <p>
                    Estimated {result.type === "solar" ? "units" : result.type === "wind" ? "turbines" : "campuses"}:{" "}
                    {result.assetCount.toLocaleString()}
                  </p>
                )}
                {result.installedCapacityKw && (
                  <p>Installed capacity: {result.installedCapacityKw.toLocaleString()} kW</p>
                )}
                {result.annualMWh && (
                  <p>Estimated annual generation: {result.annualMWh.toLocaleString()} MWh</p>
                )}
                <p>Estimated project cost: ${result.totalCost.toLocaleString()}</p>
                <p>{result.suitabilityReason}</p>
                <p>
                  Trend period: {result.trendPeriodStart} to {result.trendPeriodEnd}
                </p>
                {result.dailyGeneration?.length > 0 && (
                  <p>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={onOpenTrend}
                    >
                      Open daily trend graph
                    </button>
                  </p>
                )}
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}

export default ControlPanel;
