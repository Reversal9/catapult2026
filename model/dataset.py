import torch
from torch.utils.data import random_split
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
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

CLIMATE_FEATURES = ["climate_annual_temperature_c", "climate_annual_relative_humidity_pct", "climate_annual_total_precipitation_mm", "climate_total_total_precipitation_mm", "climate_annual_snowfall_mm", "climate_total_snowfall_mm", "climate_annual_cloud_cover_pct", "era5_distance_km"]
DATA_FEATURES = ["p_area", "p_tilt", "p_azimuth"]
OUTPUT_FEATURES = ["avg_annual_generation"]
ORIG_SOLAR_COLS =  DATA_FEATURES + ["ylat", "xlong", "p_img_date", "eia_id"]

def process_solar_data():

    raw_solar_df = pd.read_csv("data/solar.csv")
    raw_solar_era5_df = pd.read_csv("data/solar_with_era5_climate.csv")

    cols_not_in_list = [col for col in raw_solar_df.columns if col not in ORIG_SOLAR_COLS]
    raw_solar_era5_df = raw_solar_era5_df.drop(columns=cols_not_in_list)

    #eia_ids = raw_solar_era5_df["eia_id"].dropna().unique().tolist()
    # avg_generation_df = utils.get_all_generation(eia_ids)
    avg_generation_df = pd.read_csv("data/avg_eia_solar_gen.csv") # Maybe in future change to live solar

    raw_solar_era5_df = raw_solar_era5_df.merge(avg_generation_df, left_on="eia_id", right_on="plantCode", how="left")

    #Final DF - Input + Output features
    final_df = raw_solar_era5_df[DATA_FEATURES + CLIMATE_FEATURES + OUTPUT_FEATURES]
    final_df.to_csv("data/processed/solar.csv", index=False)

def get_data(path="data/processed/solar.csv", feature_cols=DATA_FEATURES + CLIMATE_FEATURES + OUTPUT_FEATURES, label_col="avg_annual_generation", batch_size=32, train_frac=0.8):
    
    df = pd.read_csv(path)
    
    df.fillna(0, inplace=True)
    
    df = df.sample(frac=1).reset_index(drop=True)
    
    X = df[feature_cols].values
    train_size = int(train_frac * len(df))
    scaler = StandardScaler()
    scaler.fit(X[:train_size])
    df[feature_cols] = scaler.transform(X)

    dataset = RenewableDataset(df, feature_cols, label_col)
    
    train_dataset = torch.utils.data.Subset(dataset, range(train_size))
    test_dataset  = torch.utils.data.Subset(dataset, range(train_size, len(dataset)))
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader  = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    input_size = len(feature_cols)
    
    return train_loader, test_loader, input_size