from __future__ import annotations

from pathlib import Path
import torch
from torch.utils.data import random_split
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import utils

from era5 import ERA5_CLIMATE_FEATURES, SOLAR_WITH_ERA5_PATH

class RenewableDataset(Dataset):
    def __init__(self, df, feature_cols, target_col):
        self.features = torch.tensor(df[feature_cols].values, dtype=torch.float32)
        self.targets  = torch.tensor(df[target_col].values,  dtype=torch.float32)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

def process_solar_data():

    final_df = None


    DATA_FEATURES = ["p_area", "p_tilt", "p_azimuth"]
    ORIG_SOLAR_COLS =  DATA_FEATURES + ["ylat", "xlong", "p_img_date", "eia_id"]

    raw_solar_df = pd.read_csv("data/solar_with_climate.csv")
    raw_solar_era5_df = pd.read_csv("data/solar_with_era5_climate.csv")

    cols_not_in_list = [col for col in raw_solar_df.columns if col not in DATA_FEATURES]
    raw_solar_era5_df = raw_solar_era5_df.drop(columns=cols_not_in_list)

    eia_ids = raw_solar_era5_df["eia_id"].dropna().unique().tolist()
    avg_generation_df = utils.get_all_generation(eia_ids)

    raw_solar_era5_df = raw_solar_era5_df.merge(avg_generation_df, left_on="eia_id", right_on="plantCode", how="left")

    

def get_data():
    df = pd.read_csv("data/dataset_sc.csv")
    df = df.sample(frac=1).reset_index(drop=True)


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

    return train_loader, test_loader

process_solar_data()
