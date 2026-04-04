import torch
from torch.utils.data import random_split
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import model.utils as utils

class RenewableDataset(Dataset):
    def __init__(self, df, feature_cols, target_col):
        self.features = torch.tensor(df[feature_cols].values, dtype=torch.float32)
        self.targets  = torch.tensor(df[target_col].values,  dtype=torch.float32)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

def get_data():

    raw_df = pd.read_csv("solar.csv")["ylat", "xlong", "p_img_date"]
    df = pd.DataFrame(columns=utils.get_solar_weather_features())
    for i in range(0, raw_df.shape[0]):
        df[df.shape[0]] = utils.get_solar_weather_data(raw_df.iloc[i, "ylat"], raw_df.iloc[i, "xlong"], raw_df.iloc[i, "p_img_date"])
    df = df.sample(frac=1).reset_index(drop=True)

    solar_feature_cols = [
        "p_area"
    ] + utils.get_solar_weather_features()

    dataset = RenewableDataset(df, solar_feature_cols, "p_cap_ac")
    train_size = int(0.8 * len(dataset))
    test_size  = len(dataset) - train_size

    train_dataset = torch.utils.data.Subset(dataset, range(train_size))
    test_dataset  = torch.utils.data.Subset(dataset, range(test_size, len(dataset)))

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=False)
    test_loader  = DataLoader(test_dataset,  batch_size=32, shuffle=False)

    return train_loader, test_loader