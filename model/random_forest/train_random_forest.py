from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import model.random_forest.dataset_random_forest as dataset_random_forest
import model.era5_dataset_code.era5 as era5


MODEL_DIR = Path(__file__).resolve().parent


def train_model(
    dataset_path: Path = era5.SOLAR_WITH_ERA5_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 300,
    max_depth: int | None = 20,
):
    df = dataset_random_forest.load_training_dataframe(dataset_path=dataset_path)
    feature_columns = dataset_random_forest.get_training_feature_columns()

    X = df[feature_columns]
    y = df["p_cap_ac"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
    )

    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = MODEL_DIR / f"solar_random_forest_{timestamp}.joblib"
    payload = {
        "model": model,
        "feature_columns": feature_columns,
        "metrics": {
            "mse": mse,
            "mae": mae,
            "r2": r2,
        },
    }
    joblib.dump(payload, model_path)

    print(f"rows={len(df)}")
    print(f"mse={mse:.4f}")
    print(f"mae={mae:.4f}")
    print(f"r2={r2:.4f}")
    print(f"saved_model={model_path}")
    return model_path


def parse_args():
    parser = argparse.ArgumentParser(description="Download ERA5, merge climate into solar.csv, and train a baseline model.")
    parser.add_argument("--download-era5", action="store_true", help="Download monthly ERA5 means into data/")
    parser.add_argument("--build-lookup", action="store_true", help="Build the nearest-cell ERA5 climate lookup CSV")
    parser.add_argument("--build-dataset", action="store_true", help="Merge solar.csv with the ERA5 lookup")
    parser.add_argument("--era5-path", type=Path, default=era5.ERA5_RAW_PATH, help="Path to the ERA5 NetCDF file")
    parser.add_argument("--dataset-path", type=Path, default=era5.SOLAR_WITH_ERA5_PATH, help="Path to the merged dataset CSV")
    parser.add_argument("--test-size", type=float, default=0.2, help="Fraction reserved for evaluation")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed")
    parser.add_argument("--n-estimators", type=int, default=300, help="Random forest tree count")
    parser.add_argument("--max-depth", type=int, default=20, help="Random forest max depth")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.download_era5:
        era5.download_era5_monthly_means(output_path=args.era5_path)

    if args.build_lookup:
        era5.build_era5_climate_lookup(era5_path=args.era5_path, output_path=era5.ERA5_LOOKUP_PATH)
        era5.clean_era5_climate_lookup(
            lookup_csv_path=era5.ERA5_LOOKUP_PATH,
            output_path=era5.ERA5_LOOKUP_CLEAN_PATH,
        )

    if args.build_dataset:
        era5.build_solar_with_era5_dataset(
            era5_path=args.era5_path,
            lookup_csv_path=era5.ERA5_LOOKUP_CLEAN_PATH,
            output_path=args.dataset_path,
        )

    train_model(
        dataset_path=args.dataset_path,
        test_size=args.test_size,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
    )


if __name__ == "__main__":
    main()
