"""
Solar panel spec scraper — CLI entry point.

Usage:
    # Single panel → stdout
    python -m fetch.scraper "REC Solar REC250PE-BLK - 250 Watt BLACK FRAME Solar Panel"

    # Single panel → file
    python -m fetch.scraper "REC Solar REC250PE-BLK" --output rec250.json

    # Batch (one model per line in panels.txt) → stdout
    python -m fetch.scraper --batch panels.txt

    # Batch → file
    python -m fetch.scraper --batch panels.txt --output results.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

from .models import PanelSpec
from .sources import enfsolar, pdf as pdf_source, html_generic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_core_fields(data: dict) -> bool:
    """True if at least power *or* dimensions were successfully extracted."""
    return bool(
        data.get("power_stc_w")
        or (data.get("dimensions_mm") or {}).get("length_mm")
    )


def _merge(base: dict, overlay: dict) -> dict:
    """Fill None / empty values in `base` with values from `overlay`."""
    merged = dict(base)
    for key, val in overlay.items():
        if key in ("dimensions_mm", "operating_temp_c"):
            merged[key] = merged.get(key) or {}
            for sub_k, sub_v in (val or {}).items():
                if not merged[key].get(sub_k):
                    merged[key][sub_k] = sub_v
        elif key == "certifications":
            existing = set(merged.get(key) or [])
            merged[key] = list(existing | set(val or []))
        elif not merged.get(key):
            merged[key] = val
    return merged


def _populate(spec: PanelSpec, data: dict) -> None:
    """Write extracted field values into a PanelSpec instance."""
    dims = data.get("dimensions_mm") or {}
    spec.dimensions_mm.length_mm = dims.get("length_mm")
    spec.dimensions_mm.width_mm  = dims.get("width_mm")
    spec.dimensions_mm.depth_mm  = dims.get("depth_mm")

    spec.weight_kg                  = data.get("weight_kg")
    spec.power_stc_w                = data.get("power_stc_w")
    spec.efficiency_pct             = data.get("efficiency_pct")
    spec.voc_v                      = data.get("voc_v")
    spec.vmp_v                      = data.get("vmp_v")
    spec.isc_a                      = data.get("isc_a")
    spec.imp_a                      = data.get("imp_a")
    spec.temp_coeff_pmax_pct_per_c  = data.get("temp_coeff_pmax_pct_per_c")
    spec.max_system_voltage_v       = data.get("max_system_voltage_v")
    spec.certifications             = data.get("certifications") or []
    spec.price_usd                  = data.get("price_usd")
    spec.price_per_watt_usd         = data.get("price_per_watt_usd")

    temp = data.get("operating_temp_c") or {}
    spec.operating_temp_c.min_c = temp.get("min_c")
    spec.operating_temp_c.max_c = temp.get("max_c")


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def scrape_panel(model: str, verbose: bool = True) -> PanelSpec:
    """
    Run the full scraping pipeline for a single panel model string.
    Source priority: ENF Solar → PDF datasheet → generic HTML.
    """
    spec = PanelSpec(model=model)
    data: dict | None = None
    url: str | None = None
    source_type: str = "unknown"

    # 1 — ENF Solar (structured tables, most reliable for specs)
    if verbose:
        print(f"\n[scraper] {model}")
        print("  [1/3] ENF Solar...")
    data, url = enfsolar.fetch(model)
    if data:
        source_type = "enfsolar"

    # 2 — PDF datasheet
    if not data or not _has_core_fields(data):
        if verbose:
            print("  [2/3] PDF datasheet...")
        pdf_data, pdf_url = pdf_source.fetch(model)
        if pdf_data:
            if data:
                data = _merge(data, pdf_data)   # fill gaps from PDF
            else:
                data, url, source_type = pdf_data, pdf_url, "pdf_datasheet"

    # 3 — Generic HTML page
    if not data or not _has_core_fields(data):
        if verbose:
            print("  [3/3] Generic HTML...")
        html_data, html_url = html_generic.fetch(model)
        if html_data:
            if data:
                data = _merge(data, html_data)
            else:
                data, url, source_type = html_data, html_url, "html_page"

    if not data:
        if verbose:
            print("  [!] No specs found.")
        return spec

    # Price — run a dedicated retailer search if price not yet found
    if not data.get("price_usd"):
        if verbose:
            print("  [+] Searching for price...")
        price, ppw, _ = html_generic.fetch_price(model)
        if price:
            data["price_usd"] = price
            data["price_per_watt_usd"] = ppw

    spec.source_url  = url
    spec.source_type = source_type
    _populate(spec, data)
    return spec


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape standardised solar panel specs from the web.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "model",
        nargs="?",
        help='Panel model name, e.g. "REC Solar REC250PE-BLK"',
    )
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="Text file with one panel model per line",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write JSON to this file (default: output/<model-slug>.json)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages",
    )
    args = parser.parse_args()

    if not args.model and not args.batch:
        parser.print_help()
        sys.exit(1)

    verbose = not args.quiet

    # Collect models
    models: list[str] = []
    if args.model:
        models.append(args.model)
    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"Error: batch file not found: {args.batch}", file=sys.stderr)
            sys.exit(1)
        models.extend(
            line.strip()
            for line in batch_path.read_text().splitlines()
            if line.strip()
        )

    # Scrape
    results: list[dict] = []
    for i, model in enumerate(models):
        spec = scrape_panel(model, verbose=verbose)
        results.append(spec.to_dict())
        if i < len(models) - 1:
            time.sleep(1.5)  # polite delay between requests

    # Output
    payload = results[0] if len(results) == 1 else results
    output = json.dumps(payload, indent=2)

    if args.output:
        out_path = Path(args.output)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if len(models) == 1:
            slug = re.sub(r"[^\w\-]+", "_", models[0].strip().lower())[:60]
            out_path = OUTPUT_DIR / f"{slug}.json"
        else:
            out_path = OUTPUT_DIR / "batch_results.json"

    out_path.write_text(output)
    if verbose:
        print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
