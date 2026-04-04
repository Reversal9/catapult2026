# Catapult 2026 — Renewables Project

> Hackathon: 24-hour build. Model-first. Everything else supports the model.
> Scope: US only. Mode: site scouting within a user-defined radius.

---

## 1. Model Overview (START HERE)

**What it does:**
The user clicks a point on a US map and defines a search radius (default 50 miles).
The model determines:
- Whether the location is suitable for renewables at all
- If so, which type (solar or wind) maximises energy production
- A suitability score and the best candidate location within the circle

```
Input:  center_lat, center_lon, radius_miles (default 50)

Output:
  recommendation:      "solar" | "wind" | "hybrid" | "not suitable"
  best_location:       {lat, lon}          ← pinned on map
  solar_kwh_yr:        float               ← physics estimate if solar/hybrid
  wind_kwh_yr:         float               ← physics estimate if wind/hybrid
  suitability_score:   float [0–100]       ← derived from classifier probability
  confidence:          "high" | "medium" | "low"
```

**Core ML strategy — multi-class classifier:**

A single `RandomForestClassifier` is trained on real US installation locations.
The key insight: **solar farms were built where solar conditions are best; wind turbines where wind conditions are best; everywhere else was passed over.** This gives us natural labels.

```
Training labels:
  "solar"   ← locations of real solar farms     (solar.csv,  5,712 points)
  "wind"    ← locations of real wind turbines   (wind.csv,  75,727 points)
  "neither" ← random US locations with no installations nearby
```

The classifier outputs **class probabilities**:
- `P(solar)`, `P(wind)`, `P(neither)` for a given location + weather
- `recommendation = argmax(P(solar), P(wind))` — but only if `P(neither)` is not dominant
- `suitability_score = (1 − P(neither)) × 100`

Energy estimates (kWh/yr) are computed **after** classification using simple physics
formulas, driven by the weather features already fetched. ML decides *what*; physics
estimates *how much*.

---

## 2. Datasets

| File | Rows | Columns used |
|------|------|-------------|
| `solar.csv` | 5,712 | `ylat`, `xlong` |
| `wind.csv` | 75,727 | `ylat`, `xlong` |

The installation coordinates are the training signal. Capacity and turbine specs are
used only in the post-classification energy estimation step.

---

## 3. Feature Design

### 3.1 Weather features (primary)

| Feature | Source | Units | Why it matters |
|---------|--------|-------|---------------|
| `ghi_annual` | Open-Meteo `shortwave_radiation` (sum, 2023) | kWh/m²/yr | Primary solar driver |
| `wind_speed_100m` | Open-Meteo `wind_speed_100m` (mean, 2023) | m/s | Primary wind driver |

### 3.2 Location features (secondary)

| Feature | Derivation | Why it matters |
|---------|-----------|---------------|
| `lat` | raw | Encodes climate zone, sun angle |
| `lon` | raw | Encodes geography (Great Plains, coasts, mountains) |

> **Terrain note:** Elevation and slope would improve the model but require an
> additional dataset. `lat`/`lon` implicitly captures much of this (Rocky Mountains,
> Great Plains, Gulf Coast) and is sufficient for a hackathon. Add terrain as a
> future enhancement if time allows.

### 3.3 Full feature vector

```python
X = [lat, lon, ghi_annual, wind_speed_100m]   # shape: (n_samples, 4)
```

---

## 4. Training Data Preparation

Training requires weather features for all installation locations. Fetching Open-Meteo
for 80k+ points is infeasible during the hackathon, so use **proxy formulas at
training time** and **real API values at inference**.

### 4.1 Weather proxies for training

```python
# GHI proxy — latitude is the dominant driver of solar irradiance
ghi_proxy = lambda lat: max(800.0, 2000.0 - 22.0 * abs(lat))   # kWh/m²/yr

# Wind proxy — Great Plains / upper Midwest are the US wind belt
def wind_proxy(lat, lon):
    base = 6.5
    if 35 < lat < 50 and -105 < lon < -85:   # Great Plains
        base += 2.0
    if lat > 45:                               # Northern latitudes
        base += 1.0
    if lon < -115 or lon > -75:               # West/East coasts
        base += 0.5
    return base
```

These proxies are coarse but sufficient for training — the model is learning geographic
patterns, and the real API values only improve accuracy at inference.

### 4.2 Negative examples ("neither")

```python
import numpy as np

# Sample random US land points
rng = np.random.default_rng(42)
n_neg = 10_000   # match rough scale of positive examples
neg_lats = rng.uniform(24.5, 49.5, n_neg)
neg_lons = rng.uniform(-124.5, -66.5, n_neg)

# Remove any point within 80 km of an existing installation
# (use BallTree on combined solar+wind coords for fast filtering)
neg_df = remove_near_installations(neg_lats, neg_lons, threshold_km=80)
```

### 4.3 Assemble training set

```python
import pandas as pd

solar_df = pd.read_csv("solar.csv")[["ylat", "xlong"]].rename(columns={"ylat":"lat","xlong":"lon"})
wind_df  = pd.read_csv("wind.csv")[["ylat", "xlong"]].rename(columns={"ylat":"lat","xlong":"lon"})

solar_df["label"] = "solar"
wind_df["label"]  = "wind"
neg_df["label"]   = "neither"

# Add proxy weather features
for df in [solar_df, wind_df, neg_df]:
    df["ghi_annual"]      = df["lat"].apply(ghi_proxy)
    df["wind_speed_100m"] = df.apply(lambda r: wind_proxy(r.lat, r.lon), axis=1)

train_df = pd.concat([solar_df, wind_df, neg_df], ignore_index=True)
```

---

## 5. Model Training

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib

features = ["lat", "lon", "ghi_annual", "wind_speed_100m"]
X = train_df[features].values
y = train_df["label"].values

clf = RandomForestClassifier(
    n_estimators=200,
    class_weight="balanced",   # compensates for wind class being 10x larger
    random_state=42,
    n_jobs=-1
)
clf.fit(X, y)
joblib.dump(clf, "renewables_model.pkl")

# Sanity check: feature importances
for name, imp in zip(features, clf.feature_importances_):
    print(f"  {name}: {imp:.3f}")
# Expected: ghi_annual and wind_speed_100m should rank highest
```

**One model, one `.pkl` file.** No separate solar/wind models.

---

## 6. Inference Pipeline

At query time, for `(center_lat, center_lon, radius_miles)`:

```python
# 1. Fetch real weather from Open-Meteo (see Section 7)
ghi_annual, wind_speed_mean = fetch_weather(center_lat, center_lon)

# 2. Classify
clf = joblib.load("renewables_model.pkl")
X_query = [[center_lat, center_lon, ghi_annual, wind_speed_mean]]

proba  = clf.predict_proba(X_query)[0]             # [P(neither), P(solar), P(wind)]
classes = clf.classes_                              # ordering depends on LabelEncoder

p = dict(zip(classes, proba))
suitability_score = round((1 - p["neither"]) * 100, 1)

# 3. Recommendation
if p["neither"] > 0.5:
    recommendation = "not suitable"
elif abs(p["solar"] - p["wind"]) < 0.15:           # too close to call
    recommendation = "hybrid"
elif p["solar"] > p["wind"]:
    recommendation = "solar"
else:
    recommendation = "wind"

# 4. Confidence label
margin = abs(p["solar"] - p["wind"])
if margin > 0.3:   confidence = "high"
elif margin > 0.1: confidence = "medium"
else:              confidence = "low"
```

---

## 7. Weather API (Open-Meteo)

**Endpoint:** `https://archive-api.open-meteo.com/v1/archive`

```python
params = {
    "latitude":   center_lat,
    "longitude":  center_lon,
    "start_date": "2023-01-01",
    "end_date":   "2023-12-31",
    "hourly":     "shortwave_radiation,wind_speed_100m",
    "timezone":   "auto"
}
# ghi_annual      = sum(response["hourly"]["shortwave_radiation"]) / 1000
# wind_speed_mean = mean(response["hourly"]["wind_speed_100m"])
```

**Fallback if API unavailable:**
```python
ghi_annual      = ghi_proxy(center_lat)
wind_speed_mean = wind_proxy(center_lat, center_lon)
```

---

## 8. Post-Classification Energy Estimation

Run only when `recommendation != "not suitable"`. Uses physics formulas on the
already-fetched weather features — no additional ML needed.

### 8.1 Solar (reference: 100 MW farm)

```python
REF_SOLAR_AREA_M2 = 1_960_784   # 100 MW at 51 W/m² median density
GHI_REF = 1750                   # US average kWh/m²/yr

solar_kwh_yr = (ghi_annual / GHI_REF) * 100_000 * 8760   # kWh/yr
```

### 8.2 Wind (reference: 20-turbine project)

```python
# Turbine specs: median from wind turbines inside the circle, else dataset defaults
turbine_cap_kw = median_turbine_cap_in_circle or 2000
n_turbines     = 20
CF             = min(0.60, max(0.05, 0.35 * (wind_speed_mean / 7.0) ** 2.5))

wind_kwh_yr = n_turbines * turbine_cap_kw * CF * 8760
```

---

## 9. Best Candidate Location

```python
solar_in_circle = haversine_filter(solar_df, center_lat, center_lon, radius_miles)
wind_in_circle  = haversine_filter(wind_df,  center_lat, center_lon, radius_miles)

if recommendation == "solar" and len(solar_in_circle) > 0:
    best_location = solar_in_circle[["lat", "lon"]].mean().to_dict()
elif recommendation == "wind" and len(wind_in_circle) > 0:
    best_location = wind_in_circle[["lat", "lon"]].mean().to_dict()
else:
    best_location = {"lat": center_lat, "lon": center_lon}
```

---

## 10. Simplifying Assumptions

| Assumption | Value | Justification |
|------------|-------|---------------|
| Training weather | proxy formulas (lat/lon based) | Avoids 80k API calls at training time |
| Negative examples | random US grid, filtered | No label noise from near-installation points |
| "Neither" threshold | P(neither) > 0.5 | Conservative — don't recommend bad sites |
| "Hybrid" margin | ΔP < 0.15 | Call hybrid when solar ≈ wind |
| Reference solar farm | 100 MW | Typical utility-scale |
| Reference wind project | 20 turbines | Typical small-to-mid project |
| Weather query | circle center only | Uniform at 50-mile scale |
| Historical year | 2023 | Recent, complete, available in Open-Meteo |

---

## 11. Minimal Data Requirements

**To train (offline, run once):**
- `solar.csv` ✓
- `wind.csv` ✓
- No API calls needed

**To serve:**
- `renewables_model.pkl` (output of training)
- Open-Meteo API (free, no key) with offline fallback

---

## 12. System Architecture

```
[Map click → center_lat, center_lon, radius_miles]
        │
        ├─ [Open-Meteo API] ──────── ghi_annual, wind_speed_mean
        │
        ├─ [renewables_model.pkl] ── predict_proba → P(solar), P(wind), P(neither)
        │                            → recommendation, suitability_score, confidence
        │
        ├─ [Physics formulas] ─────── solar_kwh_yr, wind_kwh_yr (if suitable)
        │
        ├─ [BallTree filter] ──────── best_location (centroid of in-circle installs)
        │
        └─ [JSON → Leaflet.js frontend]
```

### Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | Python + FastAPI | Fast to build, async for API calls |
| ML | scikit-learn RandomForestClassifier | No tuning needed, `predict_proba` built-in |
| Model persistence | joblib | Standard sklearn serialization |
| Geospatial filter | scikit-learn BallTree (Haversine) | Fast filter on 80k points |
| Data | pandas + numpy | CSV loading + math |
| HTTP client | httpx (async) | Non-blocking Open-Meteo calls |
| Frontend | Leaflet.js (vanilla JS) | Map + circle overlay, no framework |
| Hosting | uvicorn (local) | Sufficient for hackathon demo |

---

## 13. Implementation Plan (24-hour hackathon)

| Phase | Hours | Tasks |
|-------|-------|-------|
| **1 — Training script** | 0–3h | Feature engineering, negative sampling, train classifier, inspect feature importances, save `renewables_model.pkl` |
| **2 — Inference pipeline** | 3–6h | Load model, `predict_proba`, recommendation + suitability logic, BallTree filter for best_location |
| **3 — Weather integration** | 6–9h | Open-Meteo fetch, parse GHI + wind speed, offline fallback, end-to-end test on 5 US cities |
| **4 — FastAPI backend** | 9–12h | `POST /scout` endpoint, physics energy formulas, full JSON response |
| **5 — Frontend map UI** | 12–18h | Leaflet map, click-to-center, radius slider, draw circle, pin best_location, result card |
| **6 — Validation + polish** | 18–22h | All test cases below, edge cases, error handling |
| **7 — Demo prep** | 22–24h | Script, README, screenshots |

### Validation test cases

| Location | Radius | Expected |
|----------|--------|---------|
| Phoenix, AZ (33.4, -112.1) | 50 mi | Solar, high suitability |
| Amarillo, TX (35.2, -101.8) | 50 mi | Wind or hybrid |
| North Dakota (47.5, -100.5) | 50 mi | Wind, high suitability |
| Seattle, WA (47.6, -122.3) | 50 mi | Low suitability |
| Mojave Desert, CA (35.0, -117.5) | 50 mi | Solar, very high suitability |
| Gulf Coast, TX (27.8, -97.4) | 50 mi | Wind |
| Mid-Atlantic Ocean (38.0, -70.0) | 50 mi | Not suitable |

---

## 14. API Contract

### `POST /scout`

**Request:**
```json
{
  "lat": 33.4,
  "lon": -112.1,
  "radius_miles": 50
}
```

**Response:**
```json
{
  "recommendation": "solar",
  "best_location": { "lat": 33.41, "lon": -112.08 },
  "solar_kwh_yr": 182000000,
  "wind_kwh_yr": 91000000,
  "suitability_score": 91.2,
  "confidence": "high",
  "probabilities": { "solar": 0.78, "wind": 0.14, "neither": 0.08 },
  "n_solar_in_circle": 7,
  "n_wind_in_circle": 3,
  "ghi_annual": 2150.0,
  "wind_speed_mean": 6.2,
  "weather_source": "api"
}
```
