from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ERA5_RAW_PATH = DATA_DIR / "era5_monthly_us_1991_2020.nc"
ERA5_EXTRACT_DIR = DATA_DIR / "era5_monthly_us_1991_2020"
ERA5_LOOKUP_PATH = DATA_DIR / "era5_climate_lookup.csv"
ERA5_LOOKUP_CLEAN_PATH = DATA_DIR / "era5_climate_lookup_clean.csv"
SOLAR_WITH_ERA5_PATH = DATA_DIR / "solar_with_era5_climate.csv"
SOLAR_SOURCE_PATH = DATA_DIR / "solar.csv"

YEARS = [str(year) for year in range(1991, 2021)]
MONTHS = [f"{month:02d}" for month in range(1, 13)]
US_AREA = [49.5, -125.0, 24.0, -66.5]


ERA5_CLIMATE_FEATURES = [
    "temperature_c",
    "relative_humidity_pct",
    "total_precipitation_mm",
    "snowfall_mm",
    "cloud_cover_pct",
]

ERA5_SUM_AGGREGATE_FEATURES = {
    "total_precipitation_mm",
    "snowfall_mm",
}


def download_era5_monthly_means(
    output_path: Path = ERA5_RAW_PATH,
    area: list[float] = US_AREA,
    years: list[str] = YEARS,
):
    try:
        import cdsapi
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'cdsapi'. Install model/requirements-era5.txt and configure ~/.cdsapirc first."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = cdsapi.Client()
    request = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": [
            "2m_temperature",
            "2m_dewpoint_temperature",
            "total_precipitation",
            "snowfall",
            "total_cloud_cover",
        ],
        "year": years,
        "month": MONTHS,
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": area,
    }
    client.retrieve("reanalysis-era5-single-levels-monthly-means", request, str(output_path))
    print(f"saved_era5_file={output_path}")
    return output_path


def resolve_era5_data_files(era5_path: Path = ERA5_RAW_PATH) -> list[Path]:
    if not era5_path.exists():
        raise FileNotFoundError(f"ERA5 file not found: {era5_path}")

    with era5_path.open("rb") as handle:
        magic = handle.read(4)

    if magic != b"PK\x03\x04":
        return [era5_path]

    extract_dir = ERA5_EXTRACT_DIR
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(era5_path, "r") as archive:
        archive.extractall(extract_dir)

    extracted_candidates = sorted(
        [path for path in extract_dir.rglob("*") if path.is_file() and path.suffix in {".nc", ".grib", ".grb"}]
    )
    if extracted_candidates:
        print(f"resolved_era5_files={','.join(str(path) for path in extracted_candidates)}")
        return extracted_candidates

    extracted_files = sorted([path for path in extract_dir.rglob("*") if path.is_file()])
    if len(extracted_files) == 1:
        print(f"resolved_era5_files={extracted_files[0]}")
        return extracted_files

    raise RuntimeError(f"Could not find a usable ERA5 data file after extracting {era5_path}")


def open_era5_dataset(era5_path: Path = ERA5_RAW_PATH):
    try:
        import xarray as xr
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'xarray'. Install model/requirements-era5.txt before reading ERA5 data."
        ) from exc

    resolved_paths = resolve_era5_data_files(era5_path)
    datasets = []
    for path in resolved_paths:
        if path.suffix in {".grib", ".grb"}:
            datasets.append(xr.open_dataset(path, engine="cfgrib"))
        else:
            datasets.append(xr.open_dataset(path, engine="netcdf4"))

    if len(datasets) == 1:
        return datasets[0]

    return xr.merge(datasets, compat="override", join="outer")


def _pick_var_name(dataset, candidates: list[str]) -> str:
    for name in candidates:
        if name in dataset.data_vars:
            return name
    available = ", ".join(sorted(dataset.data_vars))
    raise KeyError(f"None of {candidates} found in ERA5 dataset. Available variables: {available}")


def _get_time_column(frame: pd.DataFrame) -> str:
    for column in ["time", "valid_time", "date"]:
        if column in frame.columns:
            return column
    raise KeyError(f"Could not find a time column in ERA5 dataframe columns: {list(frame.columns)}")


def _normalize_site_longitudes(site_lons: np.ndarray, era5_lons: np.ndarray) -> np.ndarray:
    if float(np.nanmin(era5_lons)) >= 0:
        return np.where(site_lons < 0, site_lons + 360.0, site_lons)
    return site_lons


def _nearest_indices(axis_values: np.ndarray, targets: np.ndarray) -> np.ndarray:
    distances = np.abs(axis_values.reshape(-1, 1) - targets.reshape(1, -1))
    return distances.argmin(axis=0)


def _relative_humidity_from_celsius(temp_c: pd.Series, dewpoint_c: pd.Series) -> pd.Series:
    numerator = np.exp((17.625 * dewpoint_c) / (243.04 + dewpoint_c))
    denominator = np.exp((17.625 * temp_c) / (243.04 + temp_c))
    rh = 100.0 * (numerator / denominator)
    return rh.clip(lower=0.0, upper=100.0)


def _haversine_distance_km(
    lat1_deg: pd.Series,
    lon1_deg: pd.Series,
    lat2_deg: pd.Series,
    lon2_deg: pd.Series,
) -> pd.Series:
    earth_radius_km = 6371.0088
    lat1 = np.radians(lat1_deg.astype(float))
    lon1 = np.radians(lon1_deg.astype(float))
    lat2 = np.radians(lat2_deg.astype(float))
    lon2 = np.radians(lon2_deg.astype(float))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return earth_radius_km * c


def _build_climate_row(cell_df: pd.DataFrame, era5_lat: float, era5_lon: float) -> dict:
    temp_c = cell_df["temperature_k"] - 273.15
    dewpoint_c = cell_df["dewpoint_k"] - 273.15
    transformed = pd.DataFrame(
        {
            "year": cell_df["year"],
            "month": cell_df["month"],
            "temperature_c": temp_c,
            "dewpoint_c": dewpoint_c,
            "relative_humidity_pct": _relative_humidity_from_celsius(temp_c, dewpoint_c),
            "total_precipitation_mm": cell_df["total_precipitation_m"] * 1000.0,
            "snowfall_mm": cell_df["snowfall_m"] * 1000.0,
            "cloud_cover_pct": cell_df["cloud_cover_fraction"] * 100.0,
        }
    )

    monthly_means = transformed.groupby("month", as_index=False).mean(numeric_only=True)

    row = {
        "era5_latitude": era5_lat,
        "era5_longitude": era5_lon,
    }
    for feature_name in ERA5_CLIMATE_FEATURES:
        row[f"climate_annual_{feature_name}"] = round(monthly_means[feature_name].mean(), 4)
        if feature_name in ERA5_SUM_AGGREGATE_FEATURES:
            row[f"climate_total_{feature_name}"] = round(monthly_means[feature_name].sum(), 4)
            monthly_sums = transformed.groupby("month", as_index=False)[feature_name].sum()
        for month in range(1, 13):
            month_slice = monthly_means.loc[monthly_means["month"] == month, feature_name]
            row[f"climate_m{month:02d}_{feature_name}"] = round(float(month_slice.iloc[0]), 4)
            if feature_name in ERA5_SUM_AGGREGATE_FEATURES:
                month_sum_slice = monthly_sums.loc[monthly_sums["month"] == month, feature_name]
                row[f"climate_m{month:02d}_total_{feature_name}"] = round(float(month_sum_slice.iloc[0]), 4)

    return row


def build_era5_climate_lookup(
    era5_path: Path = ERA5_RAW_PATH,
    output_path: Path = ERA5_LOOKUP_PATH,
) -> pd.DataFrame:
    try:
        import xarray as xr
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'xarray'. Install model/requirements-era5.txt before building the ERA5 lookup."
        ) from exc

    solar_df = pd.read_csv(SOLAR_SOURCE_PATH, encoding="utf-8-sig")
    solar_df["ylat"] = solar_df["ylat"].astype(float)
    solar_df["xlong"] = solar_df["xlong"].astype(float)

    dataset = open_era5_dataset(era5_path)

    latitudes = np.asarray(dataset["latitude"].values, dtype=float)
    longitudes = np.asarray(dataset["longitude"].values, dtype=float)

    normalized_lons = _normalize_site_longitudes(solar_df["xlong"].to_numpy(), longitudes)
    solar_df["era5_lat_idx"] = _nearest_indices(latitudes, solar_df["ylat"].to_numpy())
    solar_df["era5_lon_idx"] = _nearest_indices(longitudes, normalized_lons)

    unique_cells = solar_df[["era5_lat_idx", "era5_lon_idx"]].drop_duplicates().reset_index(drop=True)
    print(f"solar_rows={len(solar_df)} unique_era5_cells={len(unique_cells)}")

    temp_var = _pick_var_name(dataset, ["t2m", "2m_temperature"])
    dew_var = _pick_var_name(dataset, ["d2m", "2m_dewpoint_temperature"])
    precip_var = _pick_var_name(dataset, ["tp", "total_precipitation"])
    snow_var = _pick_var_name(dataset, ["sf", "snowfall"])
    cloud_var = _pick_var_name(dataset, ["tcc", "total_cloud_cover"])

    lookup_rows: list[dict] = []
    for index, cell in unique_cells.iterrows():
        lat_idx = int(cell["era5_lat_idx"])
        lon_idx = int(cell["era5_lon_idx"])

        cell_frame = dataset[[temp_var, dew_var, precip_var, snow_var, cloud_var]].isel(
            latitude=lat_idx,
            longitude=lon_idx,
        ).to_dataframe().reset_index()

        time_column = _get_time_column(cell_frame)
        parsed_time = pd.to_datetime(cell_frame[time_column])
        cell_frame["year"] = parsed_time.dt.year
        cell_frame["month"] = parsed_time.dt.month
        cell_frame = cell_frame.rename(
            columns={
                temp_var: "temperature_k",
                dew_var: "dewpoint_k",
                precip_var: "total_precipitation_m",
                snow_var: "snowfall_m",
                cloud_var: "cloud_cover_fraction",
            }
        )

        lookup_row = _build_climate_row(
            cell_frame,
            era5_lat=float(latitudes[lat_idx]),
            era5_lon=float(longitudes[lon_idx]),
        )
        lookup_row["era5_lat_idx"] = lat_idx
        lookup_row["era5_lon_idx"] = lon_idx
        lookup_rows.append(lookup_row)

        if (index + 1) % 100 == 0 or index + 1 == len(unique_cells):
            print(f"processed_era5_cells={index + 1}/{len(unique_cells)}")

    lookup_df = pd.DataFrame(lookup_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lookup_df.to_csv(output_path, index=False)
    print(f"saved_lookup={output_path}")
    return lookup_df


def clean_era5_climate_lookup(
    lookup_csv_path: Path = ERA5_LOOKUP_PATH,
    output_path: Path = ERA5_LOOKUP_CLEAN_PATH,
) -> pd.DataFrame:
    lookup_df = pd.read_csv(lookup_csv_path)

    ordered_columns = ["era5_latitude", "era5_longitude"]
    for feature_name in ERA5_CLIMATE_FEATURES:
        ordered_columns.append(f"climate_annual_{feature_name}")
        if feature_name in ERA5_SUM_AGGREGATE_FEATURES:
            ordered_columns.append(f"climate_total_{feature_name}")
        for month in range(1, 13):
            ordered_columns.append(f"climate_m{month:02d}_{feature_name}")
            if feature_name in ERA5_SUM_AGGREGATE_FEATURES:
                ordered_columns.append(f"climate_m{month:02d}_total_{feature_name}")

    ordered_columns.extend(["era5_lat_idx", "era5_lon_idx"])

    missing_columns = [column for column in ordered_columns if column not in lookup_df.columns]
    if missing_columns:
        raise KeyError(f"Missing expected ERA5 lookup columns: {missing_columns}")

    cleaned_df = lookup_df[ordered_columns].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(output_path, index=False)
    print(f"saved_clean_lookup={output_path}")
    return cleaned_df


def _month_to_cyclic_features(month: int) -> tuple[float, float]:
    angle = 2 * np.pi * ((month - 1) / 12)
    return float(np.sin(angle)), float(np.cos(angle))


def build_solar_with_era5_dataset(
    solar_csv_path: Path = SOLAR_SOURCE_PATH,
    era5_path: Path = ERA5_RAW_PATH,
    lookup_csv_path: Path = ERA5_LOOKUP_PATH,
    output_path: Path = SOLAR_WITH_ERA5_PATH,
) -> pd.DataFrame:
    solar_df = pd.read_csv(solar_csv_path, encoding="utf-8-sig")
    solar_df["ylat"] = solar_df["ylat"].astype(float)
    solar_df["xlong"] = solar_df["xlong"].astype(float)
    solar_df["p_img_date"] = pd.to_datetime(solar_df["p_img_date"].astype(str), format="%Y%m%d", errors="coerce")

    lookup_df = pd.read_csv(lookup_csv_path)
    lookup_df["era5_lat_idx"] = lookup_df["era5_lat_idx"].astype(int)
    lookup_df["era5_lon_idx"] = lookup_df["era5_lon_idx"].astype(int)

    try:
        import xarray as xr
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'xarray'. Install model/requirements-era5.txt before building the merged dataset."
        ) from exc

    dataset = open_era5_dataset(era5_path)
    latitudes = np.asarray(dataset["latitude"].values, dtype=float)
    longitudes = np.asarray(dataset["longitude"].values, dtype=float)
    normalized_lons = _normalize_site_longitudes(solar_df["xlong"].to_numpy(), longitudes)

    solar_df["era5_lat_idx"] = _nearest_indices(latitudes, solar_df["ylat"].to_numpy())
    solar_df["era5_lon_idx"] = _nearest_indices(longitudes, normalized_lons)

    merged_df = solar_df.merge(lookup_df, on=["era5_lat_idx", "era5_lon_idx"], how="left")
    merged_df["era5_distance_km"] = _haversine_distance_km(
        merged_df["ylat"],
        merged_df["xlong"],
        merged_df["era5_latitude"],
        merged_df["era5_longitude"],
    ).round(4)
    merged_df["install_month"] = merged_df["p_img_date"].dt.month.fillna(0).astype(int)
    merged_df["install_month_sin"] = 0.0
    merged_df["install_month_cos"] = 0.0

    for month in range(1, 13):
        mask = merged_df["install_month"] == month
        month_sin, month_cos = _month_to_cyclic_features(month)
        merged_df.loc[mask, "install_month_sin"] = month_sin
        merged_df.loc[mask, "install_month_cos"] = month_cos

    valid_months = merged_df["install_month"].between(1, 12)
    for feature_name in ERA5_CLIMATE_FEATURES:
        monthly_values = pd.Series(np.nan, index=merged_df.index, dtype=float)
        for month in range(1, 13):
            monthly_column = f"climate_m{month:02d}_{feature_name}"
            monthly_values.loc[merged_df["install_month"] == month] = merged_df.loc[
                merged_df["install_month"] == month, monthly_column
            ]

        annual_column = f"climate_annual_{feature_name}"
        monthly_values.loc[~valid_months] = merged_df.loc[~valid_months, annual_column]
        merged_df[f"climate_install_month_{feature_name}"] = monthly_values

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_csv(output_path, index=False)
    print(f"saved_merged_dataset={output_path}")
    return merged_df
