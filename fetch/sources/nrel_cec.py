"""
NREL CEC (California Energy Commission) Module Database.

20,743 panels with full electrical specs. Downloaded once and cached locally.
Source: https://raw.githubusercontent.com/NREL/SAM/develop/deploy/libraries/CEC%20Modules.csv

Columns used:
    Name         → model identifier (index)
    STC          → power_stc_w  (W)
    Length, Width → dimensions_mm (m → mm)
    A_c          → area_m2 (used to derive efficiency)
    I_sc_ref     → isc_a
    V_oc_ref     → voc_v
    I_mp_ref     → imp_a
    V_mp_ref     → vmp_v
    gamma_pmp    → temp_coeff_pmax_pct_per_c  (%/K)
    T_NOCT       → noct_c (not in PanelSpec but useful)
    N_s          → n_series_cells
"""
import io
import re
from pathlib import Path
from typing import Optional

import requests

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False

CEC_URL = (
    "https://raw.githubusercontent.com/NREL/SAM/develop/"
    "deploy/libraries/CEC%20Modules.csv"
)
_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cec_modules.csv"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

_df = None  # module-level cache once loaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(s: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to a single space."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _load_df():
    global _df
    if _df is not None:
        return _df

    if not _PANDAS:
        raise ImportError("pandas is required for NREL CEC lookups")

    # Use cached file if available
    if _CACHE_PATH.exists():
        raw = _CACHE_PATH.read_text(encoding="utf-8")
    else:
        print("  [nrel_cec] Downloading CEC module database (~5 MB)...")
        res = requests.get(CEC_URL, headers=_HEADERS, timeout=30)
        res.raise_for_status()
        raw = res.text
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(raw, encoding="utf-8")
        print(f"  [nrel_cec] Cached → {_CACHE_PATH}")

    # Row 0 = column names, row 1 = units, row 2 = internal tags — skip 1 & 2
    _df = pd.read_csv(io.StringIO(raw), skiprows=[1, 2], index_col=0)
    return _df


def _fuzzy_match(query: str, names: list[str], threshold: float = 0.55) -> Optional[str]:
    """
    Return the best-matching name from `names` for `query`, or None if below threshold.
    Uses token overlap (Jaccard) — no extra deps.
    """
    q_tokens = set(_normalise(query).split())
    best_name: Optional[str] = None
    best_score = 0.0

    for name in names:
        n_tokens = set(_normalise(name).split())
        if not q_tokens or not n_tokens:
            continue
        intersection = q_tokens & n_tokens
        union = q_tokens | n_tokens
        score = len(intersection) / len(union)
        if score > best_score:
            best_score = score
            best_name = name

    return best_name if best_score >= threshold else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch(model: str) -> tuple[dict | None, str | None]:
    """
    Look up `model` in the NREL CEC database.
    Returns (specs_dict, source_url) or (None, None).
    """
    try:
        df = _load_df()
    except Exception as e:
        print(f"  [nrel_cec] load failed: {e}")
        return None, None

    names = df.index.tolist()
    match = _fuzzy_match(model, names)
    if not match:
        return None, None

    row = df.loc[match]
    print(f"  [nrel_cec] matched → {match}")

    def _f(col) -> Optional[float]:
        try:
            v = float(row.get(col, float("nan")))
            return None if v != v else v  # NaN check
        except (TypeError, ValueError):
            return None

    stc = _f("STC")
    area = _f("A_c")  # m²
    length_m = _f("Length")
    width_m = _f("Width")

    # Efficiency = STC_W / (area_m2 * 1000 W/m²)
    efficiency: Optional[float] = None
    if stc and area and area > 0:
        efficiency = round(stc / (area * 1000) * 100, 2)

    specs = {
        "dimensions_mm": {
            "length_mm": round(length_m * 1000, 1) if length_m else None,
            "width_mm":  round(width_m  * 1000, 1) if width_m  else None,
            "depth_mm":  None,  # not in CEC database
        },
        "weight_kg":                 None,  # not in CEC database
        "power_stc_w":               stc,
        "efficiency_pct":            efficiency,
        "voc_v":                     _f("V_oc_ref"),
        "vmp_v":                     _f("V_mp_ref"),
        "isc_a":                     _f("I_sc_ref"),
        "imp_a":                     _f("I_mp_ref"),
        "temp_coeff_pmax_pct_per_c": _f("gamma_pmp"),
        "operating_temp_c":          {"min_c": None, "max_c": None},
        "max_system_voltage_v":      None,  # not in CEC database
        "certifications":            [],
        "price_usd":                 None,
        "price_per_watt_usd":        None,
    }

    source_url = (
        "https://sam.nrel.gov/component-library "
        f"(CEC Modules, entry: {match})"
    )
    return specs, source_url
