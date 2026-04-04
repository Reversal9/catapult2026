from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import model.era5_dataset_code.era5 as era5


def parse_args():
    parser = argparse.ArgumentParser(description="Download ERA5 monthly means into the data directory.")
    parser.add_argument("--output-path", type=Path, default=era5.ERA5_RAW_PATH, help="Target NetCDF path")
    return parser.parse_args()


def main():
    args = parse_args()
    era5.download_era5_monthly_means(output_path=args.output_path)


if __name__ == "__main__":
    main()
