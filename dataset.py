import torch
from torch.utils.data import random_split
from torch.utils.data import Dataset, DataLoader
import pandas as pd
from utils import get_solar_weather_features, get_wind_weather_features

class RenewableDataset(Dataset):
    def __init__(self, df, feature_cols, target_col):
        self.features = torch.tensor(df[feature_cols].values, dtype=torch.float32)
        self.targets  = torch.tensor(df[target_col].values,  dtype=torch.float32)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

def get_data():

    df = None #GET FROM ANEESH

    solar_feature_cols = [
        "p_area"
    ] + get_solar_weather_features()

    dataset = RenewableDataset(df, solar_feature_cols, "p_cap_ac")
    train_size = int(0.8 * len(dataset))
    test_size  = len(dataset) - train_size

    train_dataset = torch.utils.data.Subset(dataset, range(train_size))
    test_dataset  = torch.utils.data.Subset(dataset, range(test_size, len(dataset)))

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=False)
    test_loader  = DataLoader(test_dataset,  batch_size=32, shuffle=False)

    return train_loader, test_loader

