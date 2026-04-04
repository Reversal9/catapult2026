from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

_MODEL_DIR = Path(__file__).resolve().parents[1] / "model" / "random_forest"
_ERA5_LOOKUP_PATH = Path(__file__).resolve().parents[1] / "data" / "era5_climate_lookup.csv"

_CLIMATE_FEATURE_COLUMNS = [
    "climate_annual_temperature_c",
    "climate_annual_relative_humidity_pct",
    "climate_annual_total_precipitation_mm",
    "climate_total_total_precipitation_mm",
    "climate_annual_snowfall_mm",
    "climate_total_snowfall_mm",
    "climate_annual_cloud_cover_pct",
]


def _latest_joblib() -> Path | None:
    candidates = sorted(_MODEL_DIR.glob("*.joblib"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


class ModelPredictor:
    """
    Wraps the trained RandomForestRegressor and the ERA5 climate lookup table.

    predict() returns the model's estimate of annual generation (kWh/yr) plus
    the ERA5 climate features for the nearest grid cell so the caller can use
    them for the suitability score.
    """

    def __init__(self) -> None:
        model_path = _latest_joblib()
        if model_path is None:
            raise FileNotFoundError(f"No .joblib found in {_MODEL_DIR}")

        payload: dict[str, Any] = joblib.load(model_path)
        self._model = payload["model"]
        self._feature_columns: list[str] = payload["feature_columns"]
        self._model_name = model_path.name

        era5_df = pd.read_csv(_ERA5_LOOKUP_PATH)
        self._era5_df = era5_df.reset_index(drop=True)
        coords_rad = np.radians(era5_df[["era5_latitude", "era5_longitude"]].values)
        self._tree = BallTree(coords_rad, metric="haversine")

    @property
    def model_name(self) -> str:
        return self._model_name

    def _nearest_era5(self, lat: float, lon: float) -> tuple[pd.Series, float]:
        """Return the nearest ERA5 grid-cell row and distance in km."""
        query = np.radians([[lat, lon]])
        dist_rad, idx = self._tree.query(query, k=1)
        distance_km = float(dist_rad[0, 0]) * 6_371.0
        row = self._era5_df.iloc[int(idx[0, 0])]
        return row, distance_km

    def predict(
        self,
        lat: float,
        lon: float,
        usable_area_m2: float,
        panel_tilt_deg: float,
        panel_azimuth_deg: float,
    ) -> tuple[float, dict[str, float]]:
        """
        Returns:
            predicted_kwh_yr: model estimate of annual generation
            climate: dict of ERA5 climate features for the centroid
        """
        era5_row, era5_distance_km = self._nearest_era5(lat, lon)

        climate: dict[str, float] = {
            col: float(era5_row[col]) for col in _CLIMATE_FEATURE_COLUMNS
        }

        feature_map: dict[str, float] = {
            "p_area": usable_area_m2,
            "p_tilt": panel_tilt_deg,
            "p_azimuth": panel_azimuth_deg,
            "era5_distance_km": era5_distance_km,
            **climate,
        }

        X = pd.DataFrame([feature_map], columns=self._feature_columns)
        # Model was trained on EIA generation data which is in MWh/yr.
        predicted_mwh_yr = float(self._model.predict(X)[0])
        predicted_kwh_yr = max(0.0, predicted_mwh_yr) * 1_000.0
        return predicted_kwh_yr, climate


# Module-level singleton — initialised once when the backend starts.
_predictor: ModelPredictor | None = None


def load_predictor() -> ModelPredictor:
    """Call once at application startup."""
    global _predictor
    _predictor = ModelPredictor()
    return _predictor


def get_predictor() -> ModelPredictor | None:
    return _predictor
