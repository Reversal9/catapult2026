# Catapult 2026 — Renewables Project

> Scope: US only. Users draw a region on a map; the tool estimates solar (and wind) feasibility, energy output, and project cost.

---

## 1. What It Does

The user draws a region on a US map (rectangle, circle, or polygon). The backend:
1. Calculates the polygon area and centroid
2. Fetches real annual solar irradiance (GHI) for the centroid from Open-Meteo
3. Estimates panel count, installed capacity, annual energy output, and total project cost
4. Returns a suitability score and structured JSON response

Wind analysis exists in the frontend but is not backed by the ML model yet (uses a fixed formula: `area_km2 × 4900 MWh/yr`).

---

## 2. System Architecture

```
Frontend (React 19 + Vite + Leaflet.js)
    │  draws region → polygon points + panel/construction params
    ↓
Backend (FastAPI + uvicorn)
    │  POST /solar/analyze
    │  ├─ geometry.py        — polygon area + centroid (Shoelace formula)
    │  ├─ model_predictor.py — RF model + ERA5 BallTree lookup
    │  ├─ solar_analysis.py  — Open-Meteo GHI fetch + model inference
    │  └─ cost/cost.py       — ATB benchmarks + state multipliers + ITC incentives
    ↓
Open-Meteo Archive API (2023, free, no key)        ERA5 climate lookup (local CSV)
    hourly shortwave_radiation → GHI (kWh/m²/yr)   1,920 US grid cells, 0.25° resolution
    fallback: max(900, 2050 − 18×|lat|)             climate_annual_* features for RF model
```

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite, Leaflet.js 1.9.4, react-leaflet 5.0 |
| Backend | FastAPI 0.135, Uvicorn 0.43, Pydantic v2, httpx |
| Data | pandas, numpy |
| ML | scikit-learn (RandomForestRegressor), joblib |
| Climate data | ERA5 monthly normals 1991–2020 (local CSV, 1,920 US grid cells) |
| Model persistence | joblib (.joblib in model/random_forest/) |
| Hosting | GitHub Pages (frontend), local uvicorn (backend) |
| CI/CD | GitHub Actions (lint + test + build + deploy) |

---

## 3. API Contract

### `POST /solar/analyze`

**Request:**
```json
{
  "points": [{"lat": 43.72, "lon": -80.19}, ...],
  "panel_area_m2": 2.0,
  "panel_rating_w": 420.0,
  "panel_cost_usd": 260.0,
  "construction_cost_per_m2_usd": 140.0,
  "packing_efficiency": 0.75,
  "performance_ratio": 0.8,
  "sunlight_threshold_kwh_m2_yr": 1400.0,
  "panel_tilt_deg": 20.0,
  "panel_azimuth_deg": 180.0
}
```

**Response:**
```json
{
  "area_m2": 123456.7,
  "area_km2": 0.1235,
  "centroid": {"lat": 43.70, "lon": -80.10},
  "sunlight_intensity_kwh_m2_yr": 1350.5,
  "weather_source": "open-meteo",
  "panel_count": 46296,
  "installed_capacity_kw": 19444.3,
  "estimated_annual_output_kwh": 20880000.0,
  "panel_cost_usd": 12036960.0,
  "construction_cost_usd": 12962938.0,
  "total_project_cost_usd": 17499262.6,
  "suitability_score": 74.2,
  "suitable": true,
  "suitability_reason": "The region has enough area and sunlight for solar installation.",
  "model_source": "random-forest"
}
```

`model_source` is `"random-forest"` when the RF model is loaded, `"physics-fallback"` otherwise.

Other endpoints: `GET /` (health), `GET /health`

---

## 4. Cost Pipeline (`backend/cost/cost.py`)

Four-layer breakdown:
1. **System size** — usable area → panel count → DC capacity (kW)
2. **Base cost** — ATB benchmarks (USD/W) by tier: residential / commercial / utility
3. **Regional adjustment** — state-level cost multipliers (`state_cost_multipliers.csv`)
4. **Incentives** — federal ITC 30% (2026) + optional state rebates

Data files: `backend/cost/atb_benchmarks.csv`, `backend/cost/state_cost_multipliers.csv`

---

## 5. ML Model (`/model`)

### RandomForestRegressor — trained and serving

**Features** (11 total, exact column names the model was trained on):
```python
["p_area", "p_tilt", "p_azimuth",
 "climate_annual_temperature_c", "climate_annual_relative_humidity_pct",
 "climate_annual_total_precipitation_mm", "climate_total_total_precipitation_mm",
 "climate_annual_snowfall_mm", "climate_total_snowfall_mm",
 "climate_annual_cloud_cover_pct", "era5_distance_km"]
```

**Target:** `avg_annual_generation` in **MWh/yr** (EIA standard). Multiply by 1000 for kWh.

**Metrics (latest model):** R² = 0.82, MAE ≈ 10,662 MWh/yr

**Training** (`model/random_forest/train_random_forest.py`):
- 300 trees, max_depth=20, 80/20 split
- Saved as timestamped `.joblib` in `model/random_forest/`; backend loads the most recent by mtime

**Inference** (`backend/model_predictor.py`):
- Loads latest `.joblib` at FastAPI startup (lifespan)
- Loads `data/era5_climate_lookup.csv`, builds a `BallTree` (haversine) on 1,920 US grid cells
- `predict(lat, lon, usable_area_m2, tilt, azimuth)` → nearest ERA5 cell → feature vector → kWh/yr

**Suitability score** (ERA5-grounded, replaces the old arbitrary formula):
```python
ghi_score   = clamp((ghi_annual - 900) / 800 * 100, 0, 100)        # 60 %
cloud_score = clamp((80 - cloud_cover_pct) / 80 * 100, 0, 100)     # 30 %
temp_score  = clamp(100 - max(0, annual_temp_c - 25) * 2, 0, 100)  # 10 %
suitability = 0.6 * ghi_score + 0.3 * cloud_score + 0.1 * temp_score
```

**Data pipeline:**
- `data/solar.csv` (5,712 rows) — EIA solar farm locations + specs
- `data/era5_climate_lookup.csv` — ERA5 monthly climate normals (1991–2020), 1,920 cells
- `data/solar_with_era5_climate.csv` — merged training dataset
- `data/avg_eia_solar_gen.csv` — EIA annual generation targets (MWh/yr)
- `data/processed/solar.csv` — final feature matrix fed to training

### PyTorch path (`model/dataset.py`)
Dataset class exists for future DL experiments. Not used in serving.

---

## 6. Frontend (`/frontend`)

**Key files:**
- `src/App.jsx` (790 lines) — main app: map, drawing tools, state, results popup
- `src/lib/solarAnalysisApi.js` — API client (`POST /solar/analyze`)

**Drawing modes:** rectangle (2-point), circle (center + edge), free polygon

**UI flow:**
1. Landing overlay → fade in
2. DMS coordinate inputs (strict format validation)
3. Draw region on map
4. Select energy type (solar / wind) + panel model (predefined or custom specs)
5. "Search" → calls backend → results popup on map

**Wind in frontend:** area × 4900 MWh/km²/yr fixed formula (no backend ML).

---

## 7. Key File Paths

| Path | Purpose |
|------|---------|
| `backend/main.py` | FastAPI entry point, lifespan (model load), CORS, routes |
| `backend/model_predictor.py` | RF model + ERA5 BallTree; `load_predictor()` / `get_predictor()` |
| `backend/solar_analysis.py` | Open-Meteo GHI fetch + model inference + suitability score |
| `backend/geometry.py` | Polygon area + centroid (Shoelace) |
| `backend/cost/cost.py` | Cost estimation pipeline |
| `backend/schemas.py` | Pydantic request/response schemas |
| `model/random_forest/train_random_forest.py` | RF regressor training |
| `model/random_forest/*.joblib` | Trained models (timestamped); backend uses latest by mtime |
| `model/dataset.py` | PyTorch dataset class (future use) |
| `data/solar.csv` | 5,712 EIA solar farm locations + specs |
| `data/wind.csv` | 75,727 wind turbine locations |
| `data/era5_climate_lookup.csv` | ERA5 climate grid (1,920 cells, used at inference) |
| `data/solar_with_era5_climate.csv` | Merged training dataset |
| `data/processed/solar.csv` | Final feature matrix for training |
| `frontend/src/App.jsx` | Main React app |
| `frontend/src/lib/solarAnalysisApi.js` | Backend API client |

---

## 8. Open Items / Next Steps

- **Wind backend**: implement a proper wind analysis endpoint using `data/wind.csv` and ERA5 wind features; currently frontend-only (fixed formula)
- **Retrain with GHI feature**: `ghi_annual` is fetched from Open-Meteo at inference but is not a training feature — adding it would likely improve R²
- **PyTorch model**: complete DL training path in `model/dataset.py` and evaluate against RF baseline
- **Circle/radius mode**: currently polygon only; could add radius-based scouting if needed
