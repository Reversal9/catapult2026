export const ASSET_PRESETS = {
  solar: [
    {
      id: "sunforge_sf_450",
      label: "SunForge SF-450",
      spec: {
        panel_area_m2: 2.0,
        panel_rating_w: 450,
        panel_cost_usd: 255,
        construction_cost_per_m2_usd: 140,
        packing_efficiency: 0.75,
        performance_ratio: 0.81,
        sunlight_threshold_kwh_m2_yr: 1400,
      },
    },
    {
      id: "heliomax_hx_620",
      label: "HelioMax HX-620",
      spec: {
        panel_area_m2: 2.4,
        panel_rating_w: 620,
        panel_cost_usd: 335,
        construction_cost_per_m2_usd: 148,
        packing_efficiency: 0.74,
        performance_ratio: 0.82,
        sunlight_threshold_kwh_m2_yr: 1450,
      },
    },
    {
      id: "atlas_bifacial_ab_700",
      label: "Atlas Bifacial AB-700",
      spec: {
        panel_area_m2: 2.8,
        panel_rating_w: 700,
        panel_cost_usd: 390,
        construction_cost_per_m2_usd: 155,
        packing_efficiency: 0.72,
        performance_ratio: 0.84,
        sunlight_threshold_kwh_m2_yr: 1500,
      },
    },
  ],
  wind: [
    {
      id: "aerospin_2mw",
      label: "AeroSpin 2MW",
      spec: {
        turbine_rating_kw: 2000,
        turbine_cost_usd: 1450000,
        spacing_area_m2: 35000,
        minimum_viable_wind_speed_mps: 5.3,
      },
    },
    {
      id: "ventocore_3_5mw",
      label: "VentoCore 3.5MW",
      spec: {
        turbine_rating_kw: 3500,
        turbine_cost_usd: 1850000,
        spacing_area_m2: 45000,
        minimum_viable_wind_speed_mps: 5.8,
      },
    },
    {
      id: "skygrid_5mw",
      label: "SkyGrid 5MW",
      spec: {
        turbine_rating_kw: 5000,
        turbine_cost_usd: 2450000,
        spacing_area_m2: 60000,
        minimum_viable_wind_speed_mps: 6.2,
      },
    },
  ],
  data_center: [
    {
      id: "edgehall_compact",
      label: "EdgeHall Compact",
      spec: {
        power_density_kw_per_m2: 0.04,
        construction_cost_per_m2_usd: 260,
        fit_out_cost_per_kw_usd: 4200,
      },
    },
    {
      id: "megavault_regional",
      label: "MegaVault Regional",
      spec: {
        power_density_kw_per_m2: 0.055,
        construction_cost_per_m2_usd: 280,
        fit_out_cost_per_kw_usd: 4500,
      },
    },
    {
      id: "hyperscale_dense",
      label: "Hyperscale Dense",
      spec: {
        power_density_kw_per_m2: 0.07,
        construction_cost_per_m2_usd: 320,
        fit_out_cost_per_kw_usd: 5200,
      },
    },
  ],
};
