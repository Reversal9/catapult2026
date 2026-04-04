# Frontend

Map-first React + Vite frontend for Renewables Site Scout.

## What Users Can Do

- Select a region by rectangle, circle, or custom polygon.
- Run single-asset analysis for solar, wind, or data centers.
- Run infrastructure siting analysis for solar, wind, and data centers.
- Pick a preset or enter custom specs for the selected asset.
- Pick imagery provider and segmentation backend for infrastructure runs.
- Inspect ranked candidate sub-polygons directly on the map.
- Expand or collapse the bottom planning panel for more map space.
- Open map settings from the compact top-right popover.
- Review past-year daily generation trends for solar and wind runs.

## Main Files

- `src/App.jsx`: top-level app state
- `src/components/ControlPanel.jsx`: collapsible inputs and result summary
- `src/components/MapScene.jsx`: map layers and popups
- `src/components/TopBar.jsx`: compact settings popover
- `src/components/TrendChart.jsx`: daily generation chart
- `src/lib/assetAnalysisApi.js`: single-asset API client
- `src/lib/infrastructureAnalysisApi.js`: infrastructure API client
- `src/lib/assetResult.js`: asset-analysis mapping
- `src/lib/infrastructureResult.js`: backend result mapping
- `src/constants/infrastructureOptions.js`: provider/backend options
- `src/constants/models.js`: solar, wind, and data-center presets

## Commands

```bash
npm ci
npm run dev
npm run lint
npm run lint:fix
npm run format:check
npm run format
npm run test
npm run build
npm run preview
```

## Environment

- `VITE_BACKEND_URL`: backend base URL, defaults to `http://127.0.0.1:8000`
- `VITE_BASE_PATH`: optional deploy base path, mainly used for static hosting such as GitHub Pages

## Testing

Current UI tests cover:

- landing overlay behavior
- DMS validation
- required-field gating
- region tools toggle
- infrastructure mode readiness without a hardware model picker
- settings popover visibility
- planning-panel collapse behavior

Test file:

- `src/App.test.jsx`

## Deployment Notes

- CI and deployment workflows live in `../.github/workflows/`
- GitHub Pages deploys the production `dist` artifact
- The Pages base path is injected in CI with `VITE_BASE_PATH`
