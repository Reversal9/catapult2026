import React, { useEffect, useState } from "react";
import HelpButton from "./HelpButton";
import {
  INFRASTRUCTURE_IMAGERY_PROVIDERS,
  INFRASTRUCTURE_SEGMENTATION_OPTIONS,
  INFRASTRUCTURE_TERRAIN_PROVIDERS,
} from "../constants/infrastructureOptions";
import { generateResultInsight } from "../lib/insightText";
import { computeFinancials, computeCostBreakdown, industryBenchmark, formatUsd } from "../lib/financialProjection";

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
  terrainProvider,
  onEnergyTypeChange,
  onModelModeChange,
  onSelectedModelChange,
  onAssetSpecChange,
  onImageryProviderChange,
  onSegmentationBackendChange,
  onTerrainProviderChange,
  submitError,
  isReady,
  searching,
  result,
  selectedCandidateId,
  onSelectCandidate,
  onRunAnalysis,
  onOpenTrend,
  onOpenReport,
  onOpenAnalysis,
}) {
  const INITIAL_FILTERS = { minScore: "", maxCostM: "", minAreaKm2: "", sortBy: "score" };
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [showAll, setShowAll] = useState(false);
  const PILL_PAGE = 12;

  // Reset filters whenever a new result arrives
  useEffect(() => {
    setFilters(INITIAL_FILTERS);
    setShowAll(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const isSitingResult =
    result?.type === "infrastructure" ||
    result?.type === "solar_siting" ||
    result?.type === "wind_siting" ||
    result?.type === "data_center_siting";

  const filteredCandidates = (() => {
    if (!isSitingResult) return [];
    let list = [...(result.candidates ?? [])];
    if (filters.minScore !== "") list = list.filter((c) => c.feasibilityScore >= Number(filters.minScore));
    if (filters.maxCostM !== "") list = list.filter((c) => c.estimatedInstallationCostUsd <= Number(filters.maxCostM) * 1_000_000);
    if (filters.minAreaKm2 !== "") list = list.filter((c) => c.areaKm2 >= Number(filters.minAreaKm2));
    if (filters.sortBy === "score") list.sort((a, b) => b.feasibilityScore - a.feasibilityScore);
    else if (filters.sortBy === "cost_asc") list.sort((a, b) => a.estimatedInstallationCostUsd - b.estimatedInstallationCostUsd);
    else if (filters.sortBy === "cost_desc") list.sort((a, b) => b.estimatedInstallationCostUsd - a.estimatedInstallationCostUsd);
    else if (filters.sortBy === "area_desc") list.sort((a, b) => b.areaKm2 - a.areaKm2);
    else if (filters.sortBy === "area_asc") list.sort((a, b) => a.areaKm2 - b.areaKm2);
    return list;
  })();

  const visibleCandidates = showAll ? filteredCandidates : filteredCandidates.slice(0, PILL_PAGE);
  const hasActiveFilters = filters.minScore !== "" || filters.maxCostM !== "" || filters.minAreaKm2 !== "";

  return (
    <section
      className={`bottom-panel ${collapsed ? "collapsed" : ""}`}
      aria-label="Inputs"
    >
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
          <section className="panel-section">
            <div className="panel-section-header with-action">
              <div>
                <h3>Selection Mode</h3>
                <p>Define the area you want the backend to analyze.</p>
              </div>
              <button
                type="button"
                className={advancedOpen ? "expanded region-advanced-toggle" : "region-advanced-toggle"}
                onClick={onToggleAdvanced}
              >
                Advanced settings
              </button>
            </div>
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
                <button
                  type="button"
                  onClick={onRemoveLastPoint}
                  disabled={!hasDraftPoints}
                >
                  Undo point
                </button>
                <button type="button" onClick={onUseRectangle}>
                  Use rectangle
                </button>
              </div>
              <p className="helper">
                Use this section to switch between rectangle, circle, and
                polygon region selection. Click a coordinate field and then the
                map to fill it.
              </p>
            </div>
          </section>

          <section className="panel-section">
            <div className="panel-section-header">
              <h3>Asset Setup</h3>
              <p>Choose what you want to build and how detailed the assumptions should be.</p>
            </div>
            <div className="energy-row">
              <label>
                <HelpButton
                  label="Asset type"
                  help="Pick one asset if you want one direct estimate. Pick the comparison option if you want the backend to rank the best subregions for solar, wind, and data centers."
                />
                <select
                  value={energyType}
                  onChange={(event) => onEnergyTypeChange(event.target.value)}
                >
                  <option value="">Select asset</option>
                  <option value="solar">Solar panels</option>
                  <option value="wind">Wind turbines</option>
                  <option value="data_center">Data center</option>
                  <option value="infrastructure">
                    Compare all three across the site
                  </option>
                </select>
              </label>

              {energyType && energyType !== "infrastructure" && (
                <label>
                  <HelpButton
                    label="Specification source"
                    help="Use a preset for a fast starting point, or custom if you already know the equipment values you want to test."
                  />
                  <select
                    value={modelMode}
                    onChange={(event) => onModelModeChange(event.target.value)}
                  >
                    <option value="predefined">Use a preset</option>
                    <option value="custom">Enter custom specs</option>
                  </select>
                </label>
              )}

              {energyType &&
                energyType !== "infrastructure" &&
                modelMode === "predefined" && (
                  <label>
                    <HelpButton
                      label="Preset"
                      help="A preset fills in example equipment values so you can compare ideas without typing every input yourself."
                    />
                    <select
                      value={selectedModel}
                      onChange={(event) =>
                        onSelectedModelChange(event.target.value)
                      }
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
            </div>
          </section>

          {energyType &&
            energyType !== "infrastructure" &&
            modelMode === "custom" && (
              <section className="panel-section">
                <div className="panel-section-header">
                  <h3>Custom Specifications</h3>
                  <p>Fine-tune the main equipment values used by the estimate.</p>
                </div>
                <div className="spec-grid">
                {assetSpecFields.map((field) => (
                  <label key={field.key}>
                    <HelpButton label={field.label} help={field.help} />
                    <input
                      type="number"
                      min={field.min}
                      step={field.step ?? "any"}
                      value={field.value}
                      onChange={(event) =>
                        onAssetSpecChange(field.key, event.target.value)
                      }
                    />
                  </label>
                ))}
                </div>
              </section>
            )}

          {(energyType === "infrastructure" || energyType === "solar" || energyType === "wind" || energyType === "data_center") && (
            <section className="panel-section">
              <div className="panel-section-header">
                <h3>Data Sources</h3>
                <p>Choose the live data sources the backend should use for screening.</p>
              </div>
              <div className="spec-grid">
              <label>
                <HelpButton
                  label="Imagery provider"
                  help="USGS is the free default choice. Other providers can be used only if the backend has their credentials."
                />
                <select
                  value={imageryProvider}
                  onChange={(event) =>
                    onImageryProviderChange(event.target.value)
                  }
                >
                  {INFRASTRUCTURE_IMAGERY_PROVIDERS.map((provider) => (
                    <option key={provider.value} value={provider.value}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <HelpButton
                  label="Segmentation"
                  help="This decides how the backend detects useful surfaces such as rooftops, open land, vegetation, and water."
                />
                <select
                  value={segmentationBackend}
                  onChange={(event) =>
                    onSegmentationBackendChange(event.target.value)
                  }
                >
                  {INFRASTRUCTURE_SEGMENTATION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <HelpButton
                  label="Terrain"
                  help="Terrain slope is used to screen out steep cells before build statistics are summarized."
                />
                <select
                  value={terrainProvider}
                  onChange={(event) =>
                    onTerrainProviderChange(event.target.value)
                  }
                >
                  {INFRASTRUCTURE_TERRAIN_PROVIDERS.map((provider) => (
                    <option key={provider.value} value={provider.value}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </label>

              </div>
            </section>
          )}

          {submitError && <p className="submit-error">{submitError}</p>}

          <div className="actions-row panel-section panel-actions">
            <button
              type="button"
              className="primary"
              disabled={!isReady || searching}
              onClick={onRunAnalysis}
            >
              {searching ? "Computing..." : "Run analysis"}
            </button>
          </div>

          {isSitingResult && (
            <section
              className="candidate-results panel-section"
              aria-label="Infrastructure candidates"
            >
              <div className="candidate-summary">
                <div>
                  <strong>{result.candidateCount}</strong>{" "}
                  {result.type === "solar_siting"
                    ? "valid solar subregions"
                    : result.type === "wind_siting"
                      ? "valid wind subregions"
                      : result.type === "data_center_siting"
                        ? "valid data center subregions"
                        : "ranked candidates"}
                </div>
                <div>
                  {result.type === "solar_siting"
                    ? "These highlighted subregions passed imagery, vector, and terrain screening and were then packed with the selected solar preset."
                    : result.type === "wind_siting"
                      ? "These highlighted subregions passed imagery, vector, and terrain screening for wind turbine placement."
                      : result.type === "data_center_siting"
                        ? "These highlighted subregions passed terrain and access screening for data center siting."
                        : "Each dashed outline is a buildable subregion. The shapes inside show where the selected equipment can fit."}
                </div>
                <div>
                  Sources: {result.dataSources.imagery},{" "}
                  {result.dataSources.vector_data},{" "}
                  {result.dataSources.segmentation},{" "}
                  {result.dataSources.terrain}
                </div>
              </div>

              <div className="candidate-filters">
                <div className="candidate-filter-row">
                  <label>
                    Sort
                    <select
                      value={filters.sortBy}
                      onChange={(e) => setFilters((f) => ({ ...f, sortBy: e.target.value }))}
                    >
                      <option value="score">Score ↓</option>
                      <option value="cost_asc">Cost ↑</option>
                      <option value="cost_desc">Cost ↓</option>
                      <option value="area_desc">Area ↓</option>
                      <option value="area_asc">Area ↑</option>
                    </select>
                  </label>
                  <label>
                    Min score
                    <input
                      type="number"
                      min="0"
                      max="100"
                      placeholder="0"
                      value={filters.minScore}
                      onChange={(e) => { setShowAll(false); setFilters((f) => ({ ...f, minScore: e.target.value })); }}
                    />
                  </label>
                  <label>
                    Max cost ($M)
                    <input
                      type="number"
                      min="0"
                      placeholder="any"
                      value={filters.maxCostM}
                      onChange={(e) => { setShowAll(false); setFilters((f) => ({ ...f, maxCostM: e.target.value })); }}
                    />
                  </label>
                  <label>
                    Min area (km²)
                    <input
                      type="number"
                      min="0"
                      placeholder="0"
                      value={filters.minAreaKm2}
                      onChange={(e) => { setShowAll(false); setFilters((f) => ({ ...f, minAreaKm2: e.target.value })); }}
                    />
                  </label>
                  {hasActiveFilters && (
                    <button
                      type="button"
                      className="filter-clear-btn"
                      onClick={() => { setFilters(INITIAL_FILTERS); setShowAll(false); }}
                    >
                      Clear
                    </button>
                  )}
                </div>
                <div className="candidate-filter-count">
                  {filteredCandidates.length === result.candidateCount
                    ? `${result.candidateCount} subregions`
                    : `${filteredCandidates.length} of ${result.candidateCount} subregions`}
                </div>
              </div>

              <div className="candidate-strip">
                {visibleCandidates.map((candidate) => (
                  <button
                    key={candidate.id}
                    type="button"
                    className={
                      selectedCandidateId === candidate.id
                        ? "candidate-pill active"
                        : "candidate-pill"
                    }
                    onClick={() => onSelectCandidate(candidate.id)}
                  >
                    <span>{candidate.useLabel}</span>
                    <strong>{candidate.feasibilityScore.toFixed(1)}</strong>
                    <small>
                      {candidate.areaKm2.toFixed(2)} km² ·{" "}
                      ${(candidate.estimatedInstallationCostUsd / 1_000_000).toFixed(1)}M
                    </small>
                  </button>
                ))}
                {filteredCandidates.length === 0 && (
                  <p className="candidate-filter-empty">No subregions match the current filters.</p>
                )}
              </div>
              {filteredCandidates.length > PILL_PAGE && (
                <button
                  type="button"
                  className="filter-show-more-btn"
                  onClick={() => setShowAll((v) => !v)}
                >
                  {showAll
                    ? "Show fewer"
                    : `Show all ${filteredCandidates.length}`}
                </button>
              )}
            </section>
          )}

          {result && result.type !== "infrastructure" && (
            <section
              className="asset-result-card panel-section"
              aria-label="Asset analysis result"
            >
              {/* Header */}
                            <div className="asset-result-header">
                <div>
                  <h3>
                    {result.type === "data_center_siting"
                      ? result.label
                      : `${result.label} Summary`}
                  </h3>
                  <p>{result.scoreExplanation}</p>
                </div>

                {result.type === "data_center_siting" ? (
                  <button
                    type="button"
                    className="secondary-button report-button"
                    onClick={onOpenReport}
                  >
                    Open report
                  </button>
                ) : (
                  <div
                    className={`score-badge ${result.suitable ? "good" : "caution"}`}
                  >
                    <span>
                      {result.feasibilityScore.toFixed(0)}{" "}
                      {result.feasibilityScore >= 75
                        ? "Excellent"
                        : result.feasibilityScore >= 55
                          ? "Good"
                          : "Fair"}
                    </span>
                    <HelpButton
                      label="Feasibility score"
                      help="This score is a simple fit check from 0 to 100. Higher means the site better matches the main needs for this asset, such as space, weather, and build practicality."
                    />
                  </div>
                )}
              </div>
          

              {/* Natural language insight */}
              {(() => {
                const insight = generateResultInsight(result);
                return insight ? <p className="insight-text">{insight}</p> : null;
              })()}

              {/* Key metrics grid */}
              <div className="metric-grid">
                <div className="metric-cell">
                  <span>Selected area</span>
                  <strong>{result.areaKm2.toFixed(2)} km²</strong>
                </div>
                {result.validAreaKm2 > 0 && (
                  <div className="metric-cell">
                    <span>Buildable area</span>
                    <strong>{result.validAreaKm2.toFixed(2)} km²</strong>
                  </div>
                )}
                {result.installedCapacityKw > 0 && (
                  <div className="metric-cell">
                    <span>Capacity</span>
                    <strong>
                      {result.installedCapacityKw >= 1000
                        ? `${(result.installedCapacityKw / 1000).toFixed(1)} MW`
                        : `${Math.round(result.installedCapacityKw).toLocaleString()} kW`}
                    </strong>
                  </div>
                )}
                {result.annualMWh > 0 && (
                  <div className="metric-cell">
                    <span>Annual output</span>
                    <strong>{Math.round(result.annualMWh).toLocaleString()} MWh</strong>
                  </div>
                )}
                {result.assetCount != null && result.assetCount > 0 && (
                  <div className="metric-cell">
                    <span>
                      {result.type === "solar" || result.type === "solar_siting"
                        ? "Panels"
                        : result.type === "wind" || result.type === "wind_siting"
                          ? "Turbines"
                          : "Subregions"}
                    </span>
                    <strong>{Math.round(result.assetCount).toLocaleString()}</strong>
                  </div>
                )}
              </div>

              {/* Cost breakdown */}
              {(() => {
                const bd = computeCostBreakdown(result);
                if (!bd) return null;
                const benchmark = industryBenchmark(result);
                return (
                  <div className="cost-breakdown">
                    <h4>Cost breakdown</h4>
                    {bd.items.map((item) => (
                      <div className="cost-line" key={item.label}>
                        <span>{item.label}</span>
                        <span>{formatUsd(item.value)}</span>
                      </div>
                    ))}
                    <div className="cost-line cost-total">
                      <span>Total project cost</span>
                      <strong>{formatUsd(bd.total)}</strong>
                    </div>
                    {benchmark && <p className="benchmark-note">{benchmark}</p>}
                  </div>
                );
              })()}

              {/* Financial outlook */}
              {(() => {
                const fin = computeFinancials(result);
                if (!fin) return null;
                const omPct =
                  result.type === "solar_siting" || result.type === "solar"
                    ? "1.5"
                    : result.type === "wind_siting" || result.type === "wind"
                      ? "2.2"
                      : "2.8";
                return (
                  <div className="financial-outlook">
                    <h4>Financial outlook</h4>
                    <div className="cost-line">
                      <span>Estimated annual revenue</span>
                      <span className="fin-positive">{formatUsd(fin.annualRevenue)}/yr</span>
                    </div>
                    <div className="cost-line">
                      <span>O&amp;M ({omPct}%/yr)</span>
                      <span>{formatUsd(fin.annualOM)}/yr</span>
                    </div>
                    <div className="cost-line cost-total">
                      <span>Annual net income</span>
                      <strong className={fin.annualNet >= 0 ? "fin-positive" : "fin-negative"}>
                        {fin.annualNet >= 0 ? "+" : ""}
                        {formatUsd(fin.annualNet)}/yr
                      </strong>
                    </div>
                    {fin.breakEvenYears !== null && (
                      <div className="cost-line break-even-row">
                        <span>Payback period</span>
                        <strong className="fin-accent">
                          {fin.breakEvenYears <= 20
                            ? `~${Math.ceil(fin.breakEvenYears)} years`
                            : ">20 years"}
                        </strong>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Open analysis button */}
              <div>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={onOpenAnalysis}
                >
                  Open financial analysis →
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}

export default ControlPanel;
