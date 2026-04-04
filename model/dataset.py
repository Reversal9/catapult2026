import torch
from torch.utils.data import random_split
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import utils

class RenewableDataset(Dataset):
    def __init__(self, df, feature_cols, target_col):
        self.features = torch.tensor(df[feature_cols].values, dtype=torch.float32)
        self.targets  = torch.tensor(df[target_col].values,  dtype=torch.float32)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

def retrieve_data():
    raw_solar_df = pd.read_csv("data/solar.csv")[["ylat", "xlong", "p_img_date"]]
    #raw_wind_df = pd.read_csv("data/wind.csv")[["ylat", "xlong", "t_img_date"]]
    solar_df = pd.DataFrame(columns=utils.get_solar_weather_features())
    #wind_df = pd.DataFrame(columns=utils.get_wind_weather_features())
    
    raw_solar_df["p_img_date"] = pd.to_datetime(raw_solar_df["p_img_date"].astype(str), format="%Y%m%d", errors="coerce")
    #raw_wind_df["t_img_date"] = pd.to_datetime(raw_wind_df["t_img_date"].astype(str), format="%m/%d/%Y", errors="coerce")
    for i in range(0, raw_solar_df.shape[0]):
        solar_df.loc[solar_df.shape[0]] = utils.get_solar_climate_data(raw_solar_df.loc[i, "ylat"], raw_solar_df.loc[i, "xlong"])#, raw_solar_df.loc[i, "p_img_date"])
        #wind_df.loc[wind_df.shape[0]] = utils.get_wind_weather_data(raw_wind_df.loc[i, "ylat"], raw_wind_df.loc[i, "xlong"], raw_wind_df.loc[i, "t_img_date"])
        print("getting weather! ", i)
        solar_df.to_csv("data/dataset_sc.csv", index=False)
        #wind_df.to_csv("data/dataset_ww.csv", index=False)

def get_data():
    df = pd.read_csv("data/dataset_sc.csv")
    df = df.sample(frac=1).reset_index(drop=True)


    solar_feature_cols = ["p_area"] + utils.get_solar_weather_features()

    dataset = RenewableDataset(df, solar_feature_cols, "p_cap_ac")
    train_size = int(0.8 * len(dataset))
    test_size  = len(dataset) - train_size

    train_dataset = torch.utils.data.Subset(dataset, range(train_size))
    test_dataset  = torch.utils.data.Subset(dataset, range(test_size, len(dataset)))

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=False)
    test_loader  = DataLoader(test_dataset,  batch_size=32, shuffle=False)

    print("finished getting data!")

    return train_loader, test_loader