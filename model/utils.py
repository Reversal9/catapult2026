import requests
from collections import defaultdict
from datetime import datetime
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()

def get_eia_generation_batch(eia_ids):
    base_url = "https://api.eia.gov/v2/electricity/facility-fuel/data/"
    api_key = os.getenv("EIA_API_KEY")
    
    payload = {
        "facets": {"plantCode": [str(eid) for eid in eia_ids]},
        "data": ["generation"],
        "frequency": "annual",
        "sort": [{"column": "period", "direction": "desc"}],
        "length": 5000
    }
    
    response = requests.post(f"{base_url}?api_key={api_key}", json=payload)
    if response.status_code == 200:
        return response.json()["response"]["data"]
    print("Failed:", response.status_code, response.text)
    return None

def get_all_generation(eia_ids, years_per_plant=10, chunk_size=None):
    if chunk_size is None:
        chunk_size = 5000 // years_per_plant

    all_records = []
    for i in range(0, len(eia_ids), chunk_size):
        chunk = eia_ids[i:i + chunk_size]
        print(f"Fetching plants {i} to {i + len(chunk)}...")
        records = get_eia_generation_batch(chunk)
        if records:
            all_records.extend(records)

    df = pd.DataFrame(all_records)

    if df.empty:
        return df

    df["generation"] = pd.to_numeric(df["generation"], errors="coerce")
    df["period"] = pd.to_numeric(df["period"], errors="coerce")

    df = (
        df.sort_values("period", ascending=False)
        .groupby("plantCode")
        .head(years_per_plant)
    )
    avg_df = (
        df.groupby("plantCode", as_index=False)["generation"]
        .mean()
        .rename(columns={"generation": "avg_annual_generation"})
    )
    avg_df["plantCode"] = avg_df["plantCode"].astype(int)
    avg_df.to_csv("data/avg_eia_solar_gen.csv", index=False)

    return avg_df

def get_solar_weather_features():
    features = [
        "rain",
        "showers",
        "snowfall",
        "temperature_2m",
        "relative_humidity_2m",
        "cloud_cover",
        "cloud_cover_low",
        "cloud_cover_high",
        "cloud_cover_mid",
        "shortwave_radiation",
        "direct_radiation",
        "diffuse_radiation",
        "global_tilted_irradiance",
    ]
    return features

def get_wind_weather_features():
    features = [
        "rain",
        "showers",
        "snowfall",
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "wind_speed_80m",
        "wind_gusts_10m",
        "wind_direction_10m",
        "wind_direction_80m",
    ]
    return features
