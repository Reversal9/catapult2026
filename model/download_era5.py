from __future__ import annotations

import argparse
from pathlib import Path

import era5


def parse_args():
    parser = argparse.ArgumentParser(description="Download ERA5 monthly means into the data directory.")
    parser.add_argument("--output-path", type=Path, default=era5.ERA5_RAW_PATH, help="Target NetCDF path")
    return parser.parse_args()


def main():
    args = parse_args()
    era5.download_era5_monthly_means(output_path=args.output_path)


if __name__ == "__main__":
    main()
