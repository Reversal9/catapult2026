# Catapult 2026

Site Scouter is a map-first decision-support tool for analyzing a user-selected polygon and recommending subregions for solar panels, wind turbines, and data centers.

## What The App Does

The system accepts a polygon, validates it, subdivides it into smaller cells, and scores those cells for multiple infrastructure uses.

- Solar scoring considers rooftop/open-land area, shading, slope, and irradiance proxy.
- Wind scoring considers open land, obstruction, slope, and wind proxy.
- Data center scoring considers contiguous flat land and road access.
- The frontend renders returned candidate polygons and lets users inspect the highest-ranked cells by use type and score.
- The frontend also supports single-asset analysis for solar, wind, and data centers with preset or custom specs, plus a past-year daily generation trend where weather data applies.

## Current Pipeline

The backend pipeline is modular and now lives in `backend/infrastructure/`.

1. Polygon normalization and self-intersection checks.
2. Cell subdivision inside the polygon.
3. Imagery retrieval.
4. OSM building and road ingestion.
5. Terrain sampling for slope.
6. Segmentation or land-cover extraction.
7. Infrastructure scoring and ranked candidate output.

The main orchestrator is `backend/infrastructure/pipeline.py`.

## Data Sources

- Free default imagery: USGS `USGSImageryOnly`, which is primarily NAIP for CONUS requests.
- Optional imagery: Mapbox Static Images and Sentinel Hub Process API.
- Vectors: OpenStreetMap via Overpass.
- Terrain: OpenTopoData public API.

Undocumented Google tile scraping is intentionally not used. The backend accepts `"google"` only as a compatibility input and converts it to a supported/fallback path with notes, because the direct tile URL approach is not a supported Google Maps Platform integration.

## ML Segmentation Support

The backend supports these segmentation modes:

- `rule_based`
- `hybrid`
- `auto`
- `unet`
- `mask_rcnn`

`rule_based` and `hybrid` work out of the box. `unet` and `mask_rcnn` are wired as remote-service integrations because this repo does not ship model weights or a local inference runtime.

Remote inference env vars:

- `INFRA_UNET_ENDPOINT`
- `INFRA_MASK_RCNN_ENDPOINT`

Expected response shape:

```json
{
  "source": "unet-service",
  "cells": [
    {
      "id": "cell-1",
      "vegetation_ratio": 0.12,
      "water_ratio": 0.01,
      "impervious_ratio": 0.42,
      "shadow_ratio": 0.08,
      "building_ratio": 0.25
    }
  ]
}
```

## Repository Layout

- `backend`: FastAPI service and scoring pipeline.
- `frontend`: React + Leaflet UI.
- `model`: Existing training/data-prep experiments.
- `data`: Local datasets used by model and analysis work.

## Important Backend Files

- `backend/main.py`: API routes.
- `backend/schemas.py`: request/response models.
- `backend/asset_analysis.py`: single-asset analysis and weather-driven trend output.
- `backend/infrastructure_pipeline.py`: compatibility wrapper.
- `backend/infrastructure/providers/imagery.py`: imagery retrieval.
- `backend/infrastructure/providers/vector_data.py`: OSM ingestion.
- `backend/infrastructure/providers/terrain.py`: slope sampling.
- `backend/infrastructure/segmentation.py`: rule-based and remote ML segmentation integration.
- `backend/infrastructure/scoring.py`: feature fusion and candidate scoring.

## Important Frontend Files

- `frontend/src/App.jsx`: top-level app state and workflow.
- `frontend/src/components/ControlPanel.jsx`: collapsible planning panel, asset specs, and result summaries.
- `frontend/src/components/MapScene.jsx`: map rendering and candidate polygons.
- `frontend/src/components/TopBar.jsx`: compact settings popover.
- `frontend/src/components/TrendChart.jsx`: past-year daily generation chart.
- `frontend/src/lib/assetAnalysisApi.js`: single-asset API client.
- `frontend/src/lib/assetResult.js`: asset-analysis result mapping.
- `frontend/src/lib/infrastructureAnalysisApi.js`: infrastructure API client.
- `frontend/src/lib/infrastructureResult.js`: backend-to-UI mapping helpers.

## Local Development

Backend:

```bash
cd backend
python -m unittest discover -s tests -p 'test_*.py'
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run test
npm run lint
npm run build
npm run dev
```

## Environment Variables

Frontend env vars:

- `VITE_BACKEND_URL`
  - Optional.
  - Defaults to `http://127.0.0.1:8000`.
  - Set this when the frontend talks to a non-local backend.
- `VITE_BASE_PATH`
  - Optional.
  - Only needed when serving the built frontend from a subpath such as GitHub Pages.

Backend env vars:

- No env vars are strictly required for local startup.
- To run the backend with the fullest live-data path, set the provider/model env vars below.

- `MAPBOX_ACCESS_TOKEN`
  - Optional. Needed only for `imagery_provider="mapbox"`.
- `MAPBOX_STYLE_OWNER`
  - Optional. Defaults to `mapbox`.
- `MAPBOX_STYLE_ID`
  - Optional. Defaults to `satellite-streets-v12`.
- `SENTINEL_HUB_CLIENT_ID`
  - Optional. Needed only for `imagery_provider="sentinel"`.
- `SENTINEL_HUB_CLIENT_SECRET`
  - Optional. Needed only for `imagery_provider="sentinel"`.
- `SENTINEL_HUB_COLLECTION`
  - Optional. Defaults to `sentinel-2-l2a`.
- `SENTINEL_LOOKBACK_DAYS`
  - Optional. Controls Sentinel date selection.
- `SENTINEL_MAX_CLOUD_COVER`
  - Optional. Controls Sentinel filtering.
- `INFRA_UNET_ENDPOINT`
  - Optional. Remote U-Net inference endpoint for `segmentation_backend="unet"` or `auto`/`hybrid`.
- `INFRA_MASK_RCNN_ENDPOINT`
  - Optional. Remote Mask R-CNN inference endpoint for `segmentation_backend="mask_rcnn"` or `auto`/`hybrid`.
- `OSM_OVERPASS_URL`
  - Optional. Defaults to the public Overpass interpreter.
- `INFRASTRUCTURE_IMAGERY_SIZE`
  - Optional. Controls imagery sample resolution for the infrastructure pipeline.

Notes:

- Past-year solar and wind trend data comes from Open-Meteo historical APIs and does not require an API key.
- The free default imagery path is `usgs`, so you can run the infrastructure endpoint without paid imagery credentials.
