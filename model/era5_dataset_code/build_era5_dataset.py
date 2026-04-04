from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import model.era5_dataset_code.era5 as era5


def parse_args():
    parser = argparse.ArgumentParser(description="Build the ERA5 lookup and merge it into solar.csv.")
    parser.add_argument("--era5-path", type=Path, default=era5.ERA5_RAW_PATH, help="Path to the ERA5 NetCDF file")
    parser.add_argument("--lookup-path", type=Path, default=era5.ERA5_LOOKUP_PATH, help="Output lookup CSV")
    parser.add_argument("--clean-lookup-path", type=Path, default=era5.ERA5_LOOKUP_CLEAN_PATH, help="Cleaned lookup CSV")
    parser.add_argument("--output-path", type=Path, default=era5.SOLAR_WITH_ERA5_PATH, help="Merged solar dataset CSV")
    return parser.parse_args()


def main():
    args = parse_args()
    era5.build_era5_climate_lookup(era5_path=args.era5_path, output_path=args.lookup_path)
    era5.clean_era5_climate_lookup(lookup_csv_path=args.lookup_path, output_path=args.clean_lookup_path)
    era5.build_solar_with_era5_dataset(
        era5_path=args.era5_path,
        lookup_csv_path=args.clean_lookup_path,
        output_path=args.output_path,
    )


if __name__ == "__main__":
    main()
