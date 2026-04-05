/**
 * Computes financial projections for energy and infrastructure projects.
 */

const ELECTRICITY_PRICE_KWH = 0.11; // $0.11/kWh mid-market US wholesale
const DC_REVENUE_PER_KW_YR = 900;   // $/kW/yr colocation gross revenue
const SOLAR_OM_RATE = 0.015;         // 1.5% of capex/yr
const WIND_OM_RATE = 0.022;          // 2.2% of capex/yr
const DC_OM_RATE = 0.028;            // 2.8% of capex/yr
const PROJECTION_YEARS = 20;

export function computeFinancials(result) {
  if (!result?.totalCost || result.totalCost <= 0) return null;

  const type = result.type;
  let annualRevenue = 0;
  let omRate = SOLAR_OM_RATE;
  let revenueNote = "";

  if (type === "solar_siting" || type === "solar") {
    annualRevenue = (result.annualMWh ?? 0) * 1000 * ELECTRICITY_PRICE_KWH;
    omRate = SOLAR_OM_RATE;
    revenueNote = `At $${ELECTRICITY_PRICE_KWH}/kWh`;
  } else if (type === "wind_siting" || type === "wind") {
    annualRevenue = (result.annualMWh ?? 0) * 1000 * ELECTRICITY_PRICE_KWH;
    omRate = WIND_OM_RATE;
    revenueNote = `At $${ELECTRICITY_PRICE_KWH}/kWh`;
  } else if (type === "data_center_siting" || type === "data_center") {
    annualRevenue = (result.installedCapacityKw ?? 0) * DC_REVENUE_PER_KW_YR;
    omRate = DC_OM_RATE;
    revenueNote = `At $${DC_REVENUE_PER_KW_YR}/kW/yr colocation`;
  } else {
    return null;
  }

  const annualOM = result.totalCost * omRate;
  const annualNet = annualRevenue - annualOM;
  const breakEvenYears = annualNet > 0 ? result.totalCost / annualNet : null;

  const cashFlowByYear = Array.from({ length: PROJECTION_YEARS }, (_, i) => ({
    year: i + 1,
    cumulative: annualNet * (i + 1) - result.totalCost,
  }));

  return {
    annualRevenue,
    annualOM,
    annualNet,
    breakEvenYears,
    cashFlowByYear,
    projectionYears: PROJECTION_YEARS,
    revenueNote,
    isEnergyProject: type !== "data_center_siting" && type !== "data_center",
  };
}

export function computeCostBreakdown(result) {
  if (!result?.totalCost) return null;
  const type = result.type;

  if (type === "solar_siting" || type === "solar") {
    const hardware = Math.round(result.totalCost * 0.47);
    return {
      items: [
        { label: "Panel hardware", value: hardware },
        { label: "Installation & civil works", value: result.totalCost - hardware },
      ],
      total: result.totalCost,
    };
  }
  if (type === "wind_siting" || type === "wind") {
    const turbines = Math.round(result.totalCost * 0.72);
    return {
      items: [
        { label: "Turbine hardware", value: turbines },
        { label: "Site prep & foundations", value: result.totalCost - turbines },
      ],
      total: result.totalCost,
    };
  }
  if (type === "data_center_siting" || type === "data_center") {
    const shell = Math.round(result.totalCost * 0.50);
    return {
      items: [
        { label: "Building shell & civil", value: shell },
        { label: "IT & power fit-out", value: result.totalCost - shell },
      ],
      total: result.totalCost,
    };
  }
  return null;
}

export function industryBenchmark(result) {
  const type = result.type;
  const kw = result.installedCapacityKw ?? 0;
  if (type === "solar_siting" || type === "solar") {
    if (kw < 100) return "Residential scale — industry range: $2.50–3.50/W installed";
    if (kw < 1_000) return "Commercial scale — industry range: $1.80–2.80/W installed";
    return "Utility scale — industry range: $1.00–1.60/W installed";
  }
  if (type === "wind_siting" || type === "wind") {
    if (kw < 10_000) return "Small wind — industry range: $1,800–2,500/kW installed";
    return "Utility wind — industry range: $1,200–1,800/kW installed";
  }
  if (type === "data_center_siting" || type === "data_center") {
    if (kw < 1_000) return "Edge DC — industry range: $5–8M per MW capacity";
    return "Hyperscale DC — industry range: $8–12M per MW capacity";
  }
  return null;
}

export function formatUsd(value) {
  if (value == null || isNaN(value)) return "—";
  if (Math.abs(value) >= 1_000_000)
    return `$${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000)
    return `$${Math.round(value / 1_000).toLocaleString()}K`;
  return `$${Math.round(value).toLocaleString()}`;
}
