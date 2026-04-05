/**
 * Generates plain-English insight summaries from analysis result objects.
 */

const HOMES_KWH_PER_YEAR = 11_000; // avg US home annual usage

function fmt(n) {
  return Math.round(n).toLocaleString();
}

export function generateResultInsight(result) {
  if (!result) return null;
  const usablePct =
    result.validAreaKm2 > 0 && result.areaKm2 > 0
      ? Math.round((result.validAreaKm2 / result.areaKm2) * 100)
      : null;
  const type = result.type;
  if (type === "solar_siting") return solarSitingInsight(result, usablePct);
  if (type === "wind_siting") return windSitingInsight(result, usablePct);
  if (type === "data_center_siting") return dcSitingInsight(result, usablePct);
  if (type === "solar") return simpleSolarInsight(result);
  if (type === "wind") return simpleWindInsight(result);
  if (type === "data_center") return simpleDcInsight(result);
  return result.suitabilityReason ?? null;
}

function solarSitingInsight(result, usablePct) {
  if (result.candidateCount === 0) {
    return `No solar-ready subregions were found in this ${result.areaKm2.toFixed(2)} km² area after terrain, shading, and land-use screening. Try a flatter site with less tree cover.`;
  }
  const areaNote =
    usablePct !== null
      ? ` (${usablePct}% of the selection)`
      : "";
  const homesNote =
    result.annualMWh > 0
      ? ` Projected annual output of ${fmt(result.annualMWh)} MWh is enough to power roughly ${fmt((result.annualMWh * 1000) / HOMES_KWH_PER_YEAR)} US homes.`
      : "";
  const quality =
    result.feasibilityScore >= 75
      ? "Strong solar resource — flat terrain, good irradiance, and low shading across valid subregions."
      : result.feasibilityScore >= 55
        ? "Viable solar site, though some subregions have shading or terrain constraints."
        : "Marginal solar site — significant shading or slope limits the buildable footprint.";
  return (
    `${result.candidateCount} solar subregion${result.candidateCount > 1 ? "s" : ""} found covering ${result.validAreaKm2.toFixed(2)} km²${areaNote}. ` +
    `${result.assetCount > 0 ? `Fits approximately ${fmt(result.assetCount)} panels at ${formatCapacityKw(result.installedCapacityKw)} installed capacity.` : ""}` +
    homesNote +
    ` ${quality}`
  );
}

function windSitingInsight(result, usablePct) {
  if (result.candidateCount === 0) {
    return `No wind-suitable subregions were found after open-land and wind-resource screening. The site may have too many obstructions or insufficient open area for turbine spacing.`;
  }
  const areaNote = usablePct !== null ? ` (${usablePct}% of the selection)` : "";
  const homesNote =
    result.annualMWh > 0
      ? ` Estimated ${fmt(result.annualMWh)} MWh/year — enough for ~${fmt((result.annualMWh * 1000) / HOMES_KWH_PER_YEAR)} homes.`
      : "";
  const quality =
    result.feasibilityScore >= 65
      ? "Wind conditions and open land area are sufficient for a practical turbine layout."
      : "Wind conditions are marginal — the site meets minimum thresholds but is not an optimal wind location.";
  return (
    `${result.candidateCount} wind subregion${result.candidateCount > 1 ? "s" : ""} covering ${result.validAreaKm2.toFixed(2)} km²${areaNote}. ` +
    `${result.assetCount > 0 ? `Accommodates ${fmt(result.assetCount)} turbine${result.assetCount > 1 ? "s" : ""} at ${formatCapacityKw(result.installedCapacityKw)} total capacity.` : ""}` +
    homesNote +
    ` ${quality}`
  );
}

function dcSitingInsight(result, usablePct) {
  if (result.candidateCount === 0) {
    return `No data center subregions cleared terrain and access screening. The site may have insufficient flat buildable land or poor road access.`;
  }
  const areaNote = usablePct !== null ? ` (${usablePct}% of the selection)` : "";
  const quality =
    result.feasibilityScore >= 65
      ? "Flat terrain, road proximity, and available land area support efficient campus construction."
      : "Site has some terrain or access constraints that will require additional civil engineering.";
  return (
    `${result.candidateCount} buildable subregion${result.candidateCount > 1 ? "s" : ""} found covering ${result.validAreaKm2.toFixed(2)} km²${areaNote}. ` +
    `${result.installedCapacityKw > 0 ? `Combined IT capacity of ${formatCapacityKw(result.installedCapacityKw)}.` : ""}` +
    ` ${quality}`
  );
}

function simpleSolarInsight(result) {
  const homes = result.annualMWh
    ? fmt((result.annualMWh * 1000) / HOMES_KWH_PER_YEAR)
    : null;
  return (
    `${result.suitable ? "Viable solar site" : "Limited solar potential"} covering ${result.areaKm2.toFixed(2)} km². ` +
    (result.assetCount ? `Estimated ${fmt(result.assetCount)} panels at ${formatCapacityKw(result.installedCapacityKw)} capacity. ` : "") +
    (homes ? `Annual output could power ~${homes} US homes. ` : "") +
    result.suitabilityReason
  );
}

function simpleWindInsight(result) {
  const homes = result.annualMWh
    ? fmt((result.annualMWh * 1000) / HOMES_KWH_PER_YEAR)
    : null;
  return (
    `${result.suitable ? "Viable wind site" : "Marginal wind potential"} covering ${result.areaKm2.toFixed(2)} km². ` +
    (result.assetCount ? `Estimated ${fmt(result.assetCount)} turbine${result.assetCount > 1 ? "s" : ""} at ${formatCapacityKw(result.installedCapacityKw)} capacity. ` : "") +
    (homes ? `Annual output could power ~${homes} US homes. ` : "") +
    result.suitabilityReason
  );
}

function simpleDcInsight(result) {
  return (
    `${result.suitable ? "Suitable data center site" : "Limited data center potential"} across ${result.areaKm2.toFixed(2)} km². ` +
    (result.installedCapacityKw ? `${formatCapacityKw(result.installedCapacityKw)} IT capacity. ` : "") +
    result.suitabilityReason
  );
}

export function generateCandidateInsight(candidate) {
  if (!candidate) return null;
  const m = candidate.metadata ?? {};
  const area = (candidate.areaKm2 * 100).toFixed(1); // ha

  if (candidate.useType === "solar") {
    const irr = m.irradiance_kwh_m2_yr ? ` at ${fmt(m.irradiance_kwh_m2_yr)} kWh/m²/yr irradiance` : "";
    const slope = m.slope_deg != null ? `, ${m.slope_deg.toFixed(1)}° average slope` : "";
    const panels = m.panel_count ? ` Space for ${fmt(m.panel_count)} panels` : "";
    return `${area} ha of buildable solar land${irr}${slope}.${panels} across this subregion.`;
  }

  if (candidate.useType === "wind") {
    const speed = m.wind_speed_100m_mps ? `${m.wind_speed_100m_mps.toFixed(1)} m/s hub-height wind` : "Wind resource";
    const cf = m.capacity_factor ? ` with ${Math.round(m.capacity_factor * 100)}% capacity factor` : "";
    const turbines = m.turbine_count ? `. Space for ${fmt(m.turbine_count)} turbine${m.turbine_count > 1 ? "s" : ""}` : "";
    const output = candidate.estimatedAnnualOutputKwh
      ? ` generating ~${fmt(candidate.estimatedAnnualOutputKwh / 1000)} MWh/yr`
      : "";
    return `${speed}${cf}${turbines}${output}.`;
  }

  if (candidate.useType === "data_center") {
    const road = m.road_distance_m != null ? `${fmt(m.road_distance_m)} m to nearest road` : "Road access confirmed";
    const slope = m.slope_deg != null ? `, ${m.slope_deg.toFixed(1)}° slope` : "";
    const cap = m.estimated_it_load_mw ? `. Supports ~${m.estimated_it_load_mw.toFixed(1)} MW IT load` : "";
    return `${area} ha buildable footprint — ${road}${slope}${cap}.`;
  }

  return candidate.reasoning?.[0] ?? null;
}

function formatCapacityKw(kw) {
  if (!kw) return "";
  if (kw >= 1000) return `${(kw / 1000).toFixed(1)} MW`;
  return `${fmt(kw)} kW`;
}
