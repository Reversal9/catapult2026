export const INFRASTRUCTURE_IMAGERY_PROVIDERS = [
  { value: "usgs", label: "USGS/NAIP (Free)" },
  { value: "sentinel", label: "Sentinel Hub" },
  { value: "mapbox", label: "Mapbox satellite" },
  { value: "none", label: "No imagery fallback" },
];

export const INFRASTRUCTURE_SEGMENTATION_OPTIONS = [
  { value: "auto", label: "Auto" },
  { value: "hybrid", label: "Hybrid" },
  { value: "rule_based", label: "Rule-based" },
  { value: "unet", label: "U-Net service" },
  { value: "mask_rcnn", label: "Mask R-CNN service" },
];
