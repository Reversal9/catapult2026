import { ASSET_PRESETS } from "../constants/models";

// Keep the form state aligned with the first preset for each asset type.
export const defaultSpec = (assetType) =>
  structuredClone(ASSET_PRESETS[assetType]?.[0]?.spec ?? {});

export const specFieldsFor = (assetType, spec) => {
  if (assetType === "solar") {
    return [
      {
        key: "panel_area_m2",
        label: "Panel area (m²)",
        value: spec.panel_area_m2,
        min: 0.1,
        step: 0.1,
        help: "Use the surface area of one panel module.",
      },
      {
        key: "panel_rating_w",
        label: "Panel rating (W)",
        value: spec.panel_rating_w,
        min: 10,
        step: 5,
        help: "Nameplate output for one panel.",
      },
      {
        key: "panel_cost_usd",
        label: "Panel cost ($)",
        value: spec.panel_cost_usd,
        min: 1,
        step: 1,
        help: "Hardware cost for one panel before construction work.",
      },
      {
        key: "packing_efficiency",
        label: "Packing efficiency",
        value: spec.packing_efficiency,
        min: 0.1,
        step: 0.01,
        help: "Share of the site that can actually hold panels after spacing and setbacks.",
      },
    ];
  }

  if (assetType === "wind") {
    return [
      {
        key: "turbine_rating_kw",
        label: "Turbine rating (kW)",
        value: spec.turbine_rating_kw,
        min: 100,
        step: 100,
        help: "Nameplate rating for one turbine.",
      },
      {
        key: "turbine_cost_usd",
        label: "Turbine cost ($)",
        value: spec.turbine_cost_usd,
        min: 10000,
        step: 10000,
        help: "Installed hardware cost per turbine.",
      },
      {
        key: "spacing_area_m2",
        label: "Spacing area (m²)",
        value: spec.spacing_area_m2,
        min: 1000,
        step: 1000,
        help: "Average land area needed to safely space one turbine.",
      },
      {
        key: "minimum_viable_wind_speed_mps",
        label: "Minimum wind speed (m/s)",
        value: spec.minimum_viable_wind_speed_mps,
        min: 1,
        step: 0.1,
        help: "Below this level the turbine is treated as a weak fit.",
      },
    ];
  }

  return [
    {
      key: "power_density_kw_per_m2",
      label: "Power density (kW/m²)",
      value: spec.power_density_kw_per_m2,
      min: 0.001,
      step: 0.001,
      help: "IT load that each square meter of built floor area can support.",
    },
    {
      key: "construction_cost_per_m2_usd",
      label: "Shell cost ($/m²)",
      value: spec.construction_cost_per_m2_usd,
      min: 1,
      step: 1,
      help: "Core building cost before server and power equipment fit-out.",
    },
    {
      key: "fit_out_cost_per_kw_usd",
      label: "Fit-out cost ($/kW)",
      value: spec.fit_out_cost_per_kw_usd,
      min: 1,
      step: 10,
      help: "Electrical and cooling build cost per delivered IT kilowatt.",
    },
  ];
};
