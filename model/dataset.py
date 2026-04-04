from __future__ import annotations

from pathlib import Path

import pandas as pd

from era5 import ERA5_CLIMATE_FEATURES, SOLAR_WITH_ERA5_PATH


BASE_SOLAR_FEATURES = [
    "ylat",
    "xlong",
    "era5_distance_km",
    "p_area",
    "p_year",
    "p_azimuth",
    "p_tilt",
    "p_cap_dc",
]


def get_training_feature_columns() -> list[str]:
    feature_columns = BASE_SOLAR_FEATURES + ["install_month_sin", "install_month_cos"]
    feature_columns.extend(f"climate_annual_{name}" for name in ERA5_CLIMATE_FEATURES)
    feature_columns.extend(f"climate_install_month_{name}" for name in ERA5_CLIMATE_FEATURES)
    return feature_columns


def load_training_dataframe(dataset_path: Path | None = None) -> pd.DataFrame:
    resolved_path = dataset_path or SOLAR_WITH_ERA5_PATH
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Missing prepared dataset at {resolved_path}. Build the ERA5-enriched solar dataset first."
        )

    feature_columns = get_training_feature_columns()
    df = pd.read_csv(resolved_path)
    model_columns = feature_columns + ["p_cap_ac"]
    df = df[model_columns].copy()
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["p_cap_ac"])
    df = df.fillna(df.median(numeric_only=True))
    return df
