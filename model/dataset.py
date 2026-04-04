import torch
from torch.utils.data import random_split
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import numpy as np
import pandas as pd
import utils

class RenewableDataset(Dataset):
    def __init__(self, df, feature_cols, target_col):
        self.features = torch.tensor(df[feature_cols].values, dtype=torch.float32)
        self.targets  = torch.tensor(df[target_col].values,  dtype=torch.float32).unsqueeze(1)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

SOLAR_CLIMATE_FEATURES = ["climate_annual_temperature_c", "climate_annual_relative_humidity_pct", "climate_annual_total_precipitation_mm", "climate_total_total_precipitation_mm", "climate_annual_snowfall_mm", "climate_total_snowfall_mm", "climate_annual_cloud_cover_pct", "era5_distance_km"]
SOLAR_DATA_FEATURES = ["p_area", "p_tilt", "p_azimuth"]
SOLAR_OUTPUT_FEATURES = ["avg_annual_generation"]
SOLAR_MODEL_FEATURES = SOLAR_DATA_FEATURES + SOLAR_CLIMATE_FEATURES

WIND_CLIMATE_FEATURES = ["climate_annual_temperature_c", "climate_annual_relative_humidity_pct", "climate_annual_total_precipitation_mm", "climate_total_total_precipitation_mm", "climate_annual_snowfall_mm", "climate_total_snowfall_mm", "climate_annual_cloud_cover_pct", "era5_distance_km"]
WIND_DATA_FEATURES = ["p_area", "p_tilt", "p_azimuth"]
WIND_OUTPUT_FEATURES = ["avg_annual_generation"]
WIND_MODEL_FEATURES = WIND_DATA_FEATURES + WIND_CLIMATE_FEATURES

def process_solar_data():

    raw_solar_era5_df = pd.read_csv("data/solar_with_era5_climate.csv")

    raw_solar_era5_df = raw_solar_era5_df[SOLAR_CLIMATE_FEATURES + SOLAR_DATA_FEATURES]
    # eia_ids = raw_solar_era5_df["eia_id"].dropna().unique().tolist()
    # avg_generation_df = utils.get_all_generation(eia_ids)
    avg_generation_df = pd.read_csv("data/avg_eia_solar_gen.csv") # Maybe in future change to live solar

    raw_solar_era5_df = raw_solar_era5_df.merge(avg_generation_df, left_on="eia_id", right_on="plantCode", how="left")

    #Final DF - Input + Output features
    final_df = raw_solar_era5_df[SOLAR_MODEL_FEATURES + SOLAR_OUTPUT_FEATURES]
    final_df.to_csv("data/processed/solar.csv", index=False)

def process_wind_data():

    raw_wind_era5_df = pd.read_csv("data/wind_with_era5_climate.csv")

    raw_wind_era5_df = raw_wind_era5_df[WIND_CLIMATE_FEATURES + SOLAR_DATA_FEATURES]
    eia_ids = raw_wind_era5_df["eia_id"].dropna().unique().tolist()
    avg_generation_df = utils.get_all_generation(eia_ids)
    avg_generation_df = pd.read_csv("data/avg_eia_wind_gen.csv") # Maybe in future change to live solar

    raw_wind_era5_df = raw_wind_era5_df.merge(avg_generation_df, left_on="eia_id", right_on="plantCode", how="left")

    #Final DF - Input + Output features
    final_df = raw_wind_era5_df[WIND_MODEL_FEATURES + WIND_DATA_FEATURES]
    final_df.to_csv("data/processed/wind.csv", index=False)

def get_data(path, feature_cols, label_col="avg_annual_generation", batch_size=32, train_frac=0.8):

    df = pd.read_csv(path)

    df = df[df[label_col].notna() & (df[label_col] > 0)].reset_index(drop=True) #delete not na
    df[label_col] = np.log1p(df[label_col]) #TODO log transform labels for now, undo LATER
    df[feature_cols] = df[feature_cols].astype(float)

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    train_size = int(train_frac * len(df))

    X = df[feature_cols].values
    y = df[label_col].values

    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]

    imputer = SimpleImputer(strategy="median") #Filling NA tilt/azimuth vals
    X_train = imputer.fit_transform(X_train)
    X_test  = imputer.transform(X_test)

    scaler = StandardScaler() #Normalize
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    train_dataset = torch.utils.data.TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)
    )
    test_dataset = torch.utils.data.TensorDataset(
        torch.tensor(X_test, dtype=torch.float32),
        torch.tensor(y_test, dtype=torch.float32).unsqueeze(1)
    )

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader  = DataLoader(test_dataset,  batch_size=batch_size, shuffle=False)

    return train_loader, test_loader, len(feature_cols)