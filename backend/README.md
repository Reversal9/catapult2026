# Backend

FastAPI service for polygon-based solar analysis and multi-use infrastructure siting.

## API Endpoints

- `GET /`
- `GET /health`
- `POST /solar/analyze`
- `POST /asset/analyze`
- `POST /infrastructure/analyze`

## Asset Analysis Request

The asset endpoint accepts:

- `asset_type`
- `points`
- `preset_name`
- `solar_spec`
- `wind_spec`
- `data_center_spec`

What it returns:

- practical build count estimate
- installed capacity estimate
- installation cost estimate
- feasibility score with plain-language explanation
- past-year daily generation trend for solar and wind
- site-fit summary for data centers

## Infrastructure Request

The infrastructure endpoint accepts:

- `points`
- `cell_size_m`
- `imagery_provider`
- `segmentation_backend`
- `terrain_provider`
- `include_debug_layers`

Current supported imagery providers:

- `usgs`
- `mapbox`
- `sentinel`
- `none`
- `google` as a compatibility input that falls back to supported behavior

Current segmentation backends:

- `auto`
- `hybrid`
- `rule_based`
- `unet`
- `mask_rcnn`

Current terrain providers:

- `opentopodata`
- `proxy`

## Module Layout

- `main.py`: route wiring
- `schemas.py`: pydantic models
- `geometry.py`: polygon math and validation
- `solar_analysis.py`: solar-only analysis
- `infrastructure_pipeline.py`: compatibility wrapper
- `infrastructure/pipeline.py`: infrastructure orchestrator
- `infrastructure/providers/imagery.py`: imagery retrieval
- `infrastructure/providers/vector_data.py`: OSM ingestion
- `infrastructure/providers/terrain.py`: slope sampling
- `infrastructure/segmentation.py`: segmentation backends
- `infrastructure/scoring.py`: feature fusion and candidate scoring
- `tests/`: backend tests

## Provider Notes

- Free default imagery uses USGS `USGSImageryOnly`, which is primarily NAIP in CONUS.
- OpenStreetMap data is retrieved from Overpass.
- OpenTopoData is used for live slope estimation.
- Open-Meteo archive data is used for past-year solar and wind trend generation in the asset endpoint.
- Mapbox and Sentinel Hub remain optional credentialed providers.
- Undocumented Google tile scraping is intentionally unsupported.

## Remote ML Notes

The repo does not include local U-Net or Mask R-CNN weights. Instead, `unet` and `mask_rcnn` modes call optional remote inference services when these env vars are present:

- `INFRA_UNET_ENDPOINT`
- `INFRA_MASK_RCNN_ENDPOINT`

Request payload shape sent to those services:

```json
{
  "bbox": { "min_lat": 0, "min_lon": 0, "max_lat": 0, "max_lon": 0 },
  "width": 256,
  "height": 256,
  "pixels": [[[0, 0, 0, 255]]],
  "cells": [
    {
      "id": "cell-1",
      "bbox": { "min_lat": 0, "min_lon": 0, "max_lat": 0, "max_lon": 0 }
    }
  ]
}
```

Expected response payload:

```json
{
  "source": "mask-rcnn-service",
  "cells": [
    {
      "id": "cell-1",
      "vegetation_ratio": 0.1,
      "water_ratio": 0.0,
      "impervious_ratio": 0.5,
      "shadow_ratio": 0.08,
      "building_ratio": 0.2
    }
  ]
}
```

If those env vars are absent, the backend falls back to rule-based segmentation and records that fact in `pipeline_notes`.

## Run

```bash
cd backend
uvicorn main:app --reload
```

## Environment Variables

None are required to boot the API locally.

Optional live-data env vars:

- `MAPBOX_ACCESS_TOKEN`
- `MAPBOX_STYLE_OWNER`
- `MAPBOX_STYLE_ID`
- `SENTINEL_HUB_CLIENT_ID`
- `SENTINEL_HUB_CLIENT_SECRET`
- `SENTINEL_HUB_COLLECTION`
- `SENTINEL_LOOKBACK_DAYS`
- `SENTINEL_MAX_CLOUD_COVER`
- `OSM_OVERPASS_URL`
- `INFRASTRUCTURE_IMAGERY_SIZE`
- `INFRA_UNET_ENDPOINT`
- `INFRA_MASK_RCNN_ENDPOINT`

## Test

```bash
cd backend
python -m unittest discover -s tests -p 'test_*.py'
```
