from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path
from statistics import median
from typing import Iterable

import requests


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ATB_OUTPUT_CSV = DATA_DIR / "atb_benchmarks.csv"
STATE_OUTPUT_CSV = DATA_DIR / "state_cost_multipliers.csv"

ATB_CANDIDATE_URLS = [
    "https://oedi-data-lake.s3.amazonaws.com/ATB/electricity/csv/{year}/ATBe.csv",
    "https://oedi-data-lake.s3.amazonaws.com/ATB/electricity/csv/{year}/ATB.csv",
]

# Berkeley Lab's public page currently redirects to a Google Drive file.
TRACKING_THE_SUN_ZIP_URL = (
    "https://drive.google.com/uc?export=download&id=1NQh4TRC_IqDz2r5vfZuxDm6LGjEuexdu"
)

ATB_TIER_BY_TECHNOLOGY = {
    "ResPV": "residential",
    "CommercialPV": "commercial",
    "UtilityPV": "utility",
}

STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}


def _download_text(url: str, timeout: int = 120) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _download_bytes(url: str, timeout: int = 300) -> bytes:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def _canonicalize(name: str) -> str:
    return "".join(char.lower() for char in name if char.isalnum())


def _match_column(fieldnames: Iterable[str], candidates: list[str]) -> str | None:
    canonical = {_canonicalize(name): name for name in fieldnames}
    for candidate in candidates:
        matched = canonical.get(_canonicalize(candidate))
        if matched:
            return matched
    return None


def refresh_atb_benchmarks(year: int, output_path: Path = ATB_OUTPUT_CSV) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for template in ATB_CANDIDATE_URLS:
        url = template.format(year=year)
        try:
            csv_text = _download_text(url)
            rows = list(csv.DictReader(io.StringIO(csv_text)))
            records: list[dict[str, str | float | int]] = []

            for technology, tier in ATB_TIER_BY_TECHNOLOGY.items():
                candidates = [
                    row for row in rows
                    if row.get("technology") == technology
                    and row.get("core_metric_parameter") == "CAPEX"
                    and row.get("core_metric_variable") == str(year)
                    and row.get("value")
                ]
                moderate_rows = [row for row in candidates if row.get("core_metric_case") == "Moderate"]
                selected = moderate_rows[0] if moderate_rows else (candidates[0] if candidates else None)

                if not selected:
                    raise ValueError(f"Could not find CAPEX benchmark for {technology} in {url}")

                records.append(
                    {
                        "source_year": year,
                        "system_tier": tier,
                        "technology": technology,
                        "benchmark_usd_per_w": round(float(selected["value"]), 4),
                        "source": f"NREL ATB {year}",
                        "notes": f"Downloaded from {url}",
                    }
                )

            with output_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "source_year",
                        "system_tier",
                        "technology",
                        "benchmark_usd_per_w",
                        "source",
                        "notes",
                    ],
                )
                writer.writeheader()
                writer.writerows(records)
            return output_path
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    raise RuntimeError("Unable to refresh ATB benchmarks.\n" + "\n".join(errors))


def _load_tracking_the_sun_rows(zip_bytes: bytes) -> tuple[list[dict[str, str]], str]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_members:
            raise ValueError("No CSV file found in Tracking the Sun archive.")

        largest_member = max(csv_members, key=lambda name: archive.getinfo(name).file_size)
        with archive.open(largest_member) as handle:
            text_stream = io.TextIOWrapper(handle, encoding="utf-8", errors="replace")
            rows = list(csv.DictReader(text_stream))
        return rows, largest_member


def refresh_state_cost_multipliers(
    source_zip: Path | None = None,
    output_path: Path = STATE_OUTPUT_CSV,
    source_year: int = 2024,
    min_samples: int = 20,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    zip_bytes = source_zip.read_bytes() if source_zip else _download_bytes(TRACKING_THE_SUN_ZIP_URL)
    rows, member_name = _load_tracking_the_sun_rows(zip_bytes)
    if not rows:
        raise ValueError("Tracking the Sun data file is empty.")

    fieldnames = rows[0].keys()
    state_col = _match_column(fieldnames, ["state", "state_abbr", "state_abbreviation"])
    price_per_w_col = _match_column(fieldnames, ["installed_price_per_w", "price_per_w", "system_price_per_w"])
    total_price_col = _match_column(fieldnames, ["total_installed_price", "installed_price", "system_price", "project_cost"])
    size_kw_col = _match_column(fieldnames, ["system_size_dc", "system_size_kw_dc", "size_kw_dc", "system_size"])

    if not state_col:
        raise ValueError("Could not identify a state column in Tracking the Sun data.")
    if not price_per_w_col and not (total_price_col and size_kw_col):
        raise ValueError(
            "Could not identify installed price columns in Tracking the Sun data. "
            "Expected either a price-per-watt column or total-price plus system-size columns."
        )

    prices_by_state: dict[str, list[float]] = {}
    all_prices: list[float] = []

    for row in rows:
        state = row.get(state_col, "").strip().upper()
        if state not in STATE_CODES:
            continue

        price_per_w: float | None = None
        if price_per_w_col:
            raw_price = row.get(price_per_w_col, "").strip()
            if raw_price:
                try:
                    price_per_w = float(raw_price)
                except ValueError:
                    price_per_w = None

        if price_per_w is None and total_price_col and size_kw_col:
            raw_total = row.get(total_price_col, "").strip()
            raw_size = row.get(size_kw_col, "").strip()
            if raw_total and raw_size:
                try:
                    total_price = float(raw_total)
                    system_size_kw = float(raw_size)
                    if system_size_kw > 0:
                        price_per_w = total_price / (system_size_kw * 1000)
                except ValueError:
                    price_per_w = None

        if price_per_w is None or price_per_w <= 0 or price_per_w > 25:
            continue

        all_prices.append(price_per_w)
        prices_by_state.setdefault(state, []).append(price_per_w)

    if not all_prices:
        raise ValueError("No valid installed-price records found in Tracking the Sun data.")

    national_median = median(all_prices)
    records: list[dict[str, str | float | int]] = []
    for state in sorted(prices_by_state):
        state_prices = prices_by_state[state]
        if len(state_prices) < min_samples:
            continue
        state_median = median(state_prices)
        records.append(
            {
                "source_year": source_year,
                "state": state,
                "cost_multiplier": round(state_median / national_median, 4),
                "sample_size": len(state_prices),
                "source": "Berkeley Lab Tracking the Sun",
                "notes": f"Derived from {member_name}; national median installed price-per-watt baseline",
            }
        )

    if not records:
        raise ValueError("No state multipliers were generated. Check source columns or lower min_samples.")

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_year", "state", "cost_multiplier", "sample_size", "source", "notes"],
        )
        writer.writeheader()
        writer.writerows(records)

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh local cost reference files from official ATB and Berkeley Lab datasets."
    )
    parser.add_argument("--atb-year", type=int, default=2024, help="ATB release year to use for benchmark refresh.")
    parser.add_argument(
        "--tracking-the-sun-zip",
        type=Path,
        default=None,
        help="Optional local path to a downloaded Tracking the Sun public data zip file.",
    )
    parser.add_argument(
        "--state-source-year",
        type=int,
        default=2024,
        help="Year label to write into the generated state multiplier CSV.",
    )
    parser.add_argument(
        "--min-state-samples",
        type=int,
        default=20,
        help="Minimum number of observations required to write a state multiplier row.",
    )
    args = parser.parse_args()

    atb_path = refresh_atb_benchmarks(year=args.atb_year)
    state_path = refresh_state_cost_multipliers(
        source_zip=args.tracking_the_sun_zip,
        source_year=args.state_source_year,
        min_samples=args.min_state_samples,
    )

    print(f"Updated ATB benchmarks: {atb_path}")
    print(f"Updated state cost multipliers: {state_path}")


if __name__ == "__main__":
    main()

