from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DATASET_PATH = DATA_DIR / "solar_with_era5_climate.csv"

BASE_FEATURES = [
    "ylat",
    "xlong",
    "era5_distance_km",
    "p_area",
    "p_year",
    "p_azimuth",
    "p_tilt",
    "p_cap_dc",
    "install_month_sin",
    "install_month_cos",
]

CLIMATE_FEATURES = [
    "climate_annual_temperature_c",
    "climate_annual_relative_humidity_pct",
    "climate_annual_total_precipitation_mm",
    "climate_total_total_precipitation_mm",
    "climate_annual_snowfall_mm",
    "climate_total_snowfall_mm",
    "climate_annual_cloud_cover_pct",
    "climate_install_month_temperature_c",
    "climate_install_month_relative_humidity_pct",
    "climate_install_month_total_precipitation_mm",
    "climate_install_month_snowfall_mm",
    "climate_install_month_cloud_cover_pct",
]


def get_training_feature_columns() -> list[str]:
    return BASE_FEATURES + CLIMATE_FEATURES


def load_training_dataframe(dataset_path: Path | None = None) -> pd.DataFrame:
    resolved_path = dataset_path or DEFAULT_DATASET_PATH
    if not resolved_path.exists():
        raise FileNotFoundError(f"Missing merged training dataset: {resolved_path}")

    df = pd.read_csv(resolved_path)
    feature_columns = get_training_feature_columns()
    model_columns = feature_columns + ["p_cap_ac"]
    df = df[model_columns].copy()
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["p_cap_ac"])
    df = df.fillna(df.median(numeric_only=True))
    return df
