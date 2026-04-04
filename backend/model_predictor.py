from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.neighbors import BallTree
from sklearn.preprocessing import StandardScaler

_MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "habakkuk" / "model.dat"
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_ERA5_LOOKUP_CANDIDATES = [
    _DATA_DIR / "era5_climate_lookup.csv",
    _DATA_DIR / "era5_climate_lookup_summarized.csv",
]
_PROCESSED_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "solar.csv"

# Must match SOLAR_MODEL_FEATURES order from model/dataset.py
_FEATURE_COLUMNS = [
    "p_area",
    "p_tilt",
    "p_azimuth",
    "climate_annual_temperature_c",
    "climate_annual_relative_humidity_pct",
    "climate_annual_total_precipitation_mm",
    "climate_total_total_precipitation_mm",
    "climate_annual_snowfall_mm",
    "climate_total_snowfall_mm",
    "climate_annual_cloud_cover_pct",
    "era5_distance_km",
]

_CLIMATE_FEATURE_COLUMNS = [c for c in _FEATURE_COLUMNS if c.startswith("climate_")]


def _resolve_era5_lookup_path() -> Path:
    for path in _ERA5_LOOKUP_CANDIDATES:
        if path.exists():
            return path

    candidate_list = ", ".join(str(path) for path in _ERA5_LOOKUP_CANDIDATES)
    raise FileNotFoundError(f"ERA5 climate lookup not found. Tried: {candidate_list}")


def _prepare_era5_lookup_frame(era5_df: pd.DataFrame) -> pd.DataFrame:
    normalized = era5_df.copy()

    # The summarized export keeps annual monthly averages but omits the total-of-monthly
    # aggregates used during training. Reconstruct them to preserve the model feature shape.
    if (
        "climate_total_total_precipitation_mm" not in normalized.columns
        and "climate_annual_total_precipitation_mm" in normalized.columns
    ):
        normalized["climate_total_total_precipitation_mm"] = (
            normalized["climate_annual_total_precipitation_mm"] * 12.0
        )

    if (
        "climate_total_snowfall_mm" not in normalized.columns
        and "climate_annual_snowfall_mm" in normalized.columns
    ):
        normalized["climate_total_snowfall_mm"] = (
            normalized["climate_annual_snowfall_mm"] * 12.0
        )

    required_columns = {
        "era5_latitude",
        "era5_longitude",
        *_CLIMATE_FEATURE_COLUMNS,
    }
    missing_columns = sorted(required_columns - set(normalized.columns))
    if missing_columns:
        raise ValueError(
            "ERA5 climate lookup is missing required columns: "
            + ", ".join(missing_columns)
        )

    return normalized


class Habakkuk(nn.Module):
    """Mirror of the architecture in model/train.py."""

    def __init__(self, input_size: int) -> None:
        super().__init__()
        self.fc1 = nn.Linear(input_size, 480)
        self.fc2 = nn.Linear(480, 100)
        self.fc3 = nn.Linear(100, 24)
        self.dropout = nn.Dropout(p=0.2)
        self.fc4 = nn.Linear(24, 6)
        self.fc5 = nn.Linear(6, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        x = F.relu(self.fc4(x))
        return self.fc5(x)


class ModelPredictor:
    """
    Wraps the Habakkuk neural network and the ERA5 climate lookup table.

    predict() returns the model's estimate of annual generation (kWh/yr) plus
    the ERA5 climate features for the nearest grid cell so the caller can use
    them for the suitability score.
    """

    def __init__(self) -> None:
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(f"Habakkuk model not found: {_MODEL_PATH}")

        # torch.save(model) pickles the class under its original __main__ namespace.
        # Register it there so unpickling resolves correctly.
        import __main__
        __main__.Habakkuk = Habakkuk

        self._model: Habakkuk = torch.load(
            _MODEL_PATH, map_location="cpu", weights_only=False
        )
        self._model.eval()
        self._model_name = "habakkuk"

        # Refit StandardScaler on the full processed CSV to approximate the
        # scaler used during training (get_data() scaled in-memory, didn't save it).
        train_df = pd.read_csv(_PROCESSED_CSV_PATH)
        train_df.fillna(0, inplace=True)
        self._scaler = StandardScaler()
        self._scaler.fit(train_df[_FEATURE_COLUMNS].values)

        era5_lookup_path = _resolve_era5_lookup_path()
        era5_df = _prepare_era5_lookup_frame(pd.read_csv(era5_lookup_path))
        self._era5_df = era5_df.reset_index(drop=True)
        coords_rad = np.radians(era5_df[["era5_latitude", "era5_longitude"]].values)
        self._tree = BallTree(coords_rad, metric="haversine")

    @property
    def model_name(self) -> str:
        return self._model_name

    def _nearest_era5(self, lat: float, lon: float) -> tuple[pd.Series, float]:
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

        raw_features = [
            usable_area_m2,
            panel_tilt_deg,
            panel_azimuth_deg,
            *[climate[col] for col in _CLIMATE_FEATURE_COLUMNS],
            era5_distance_km,
        ]

        scaled = self._scaler.transform([raw_features])
        x = torch.tensor(scaled, dtype=torch.float32)

        with torch.no_grad():
            # Model output is MWh/yr (trained on EIA generation data).
            output = self._model(x)
            flat_output = output.reshape(-1)
            if flat_output.numel() != 1:
                raise RuntimeError(
                    "Habakkuk predictor returned "
                    f"{flat_output.numel()} outputs for a single sample."
                )
            predicted_mwh_yr = float(flat_output[0].item())

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
