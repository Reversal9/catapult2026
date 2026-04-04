from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
ATB_BENCHMARKS_CSV = DATA_DIR / "atb_benchmarks.csv"
STATE_COST_MULTIPLIERS_CSV = DATA_DIR / "state_cost_multipliers.csv"

FEDERAL_ITC = {
    2024: 0.30,
    2025: 0.30,
    2026: 0.30,
    2027: 0.30,
    2028: 0.30,
    2029: 0.30,
    2030: 0.30,
    2031: 0.30,
    2032: 0.30,
    2033: 0.26,
    2034: 0.22,
}


@dataclass(frozen=True)
class SystemSize:
    n_panels: int
    panel_area_m2: float
    usable_area_m2: float
    capacity_kw_dc: float
    panel_efficiency: float
    annual_energy_kwh: float | None = None


def _require_positive(value: float, name: str) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return float(value)


def _require_ratio(value: float, name: str) -> float:
    if not 0 < value <= 1:
        raise ValueError(f"{name} must be between 0 and 1.")
    return float(value)


def _normalize_state(state: str) -> str:
    normalized = state.strip().upper()
    if not normalized:
        raise ValueError("state must be a non-empty state abbreviation.")
    return normalized


def _resolve_system_tier(capacity_kw_dc: float) -> str:
    if capacity_kw_dc <= 20:
        return "residential"
    if capacity_kw_dc <= 1000:
        return "commercial"
    return "utility"


def _require_data_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"Required data file not found: {path}. Run backend/cost/update_sources.py "
            "or restore the seeded CSVs in backend/cost/data/."
        )
    return path


@lru_cache(maxsize=1)
def load_atb_benchmarks(path: str | Path = ATB_BENCHMARKS_CSV) -> dict[str, float]:
    resolved_path = _require_data_file(Path(path))
    benchmarks: dict[str, float] = {}

    with resolved_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            tier = row["system_tier"].strip().lower()
            benchmarks[tier] = _require_positive(float(row["benchmark_usd_per_w"]), f"benchmark[{tier}]")

    if not benchmarks:
        raise ValueError(f"No benchmark rows found in {resolved_path}.")
    return benchmarks


@lru_cache(maxsize=1)
def load_state_cost_multipliers(path: str | Path = STATE_COST_MULTIPLIERS_CSV) -> dict[str, float]:
    resolved_path = _require_data_file(Path(path))
    multipliers: dict[str, float] = {}

    with resolved_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            state = _normalize_state(row["state"])
            multipliers[state] = _require_positive(float(row["cost_multiplier"]), f"cost_multiplier[{state}]")

    if not multipliers:
        raise ValueError(f"No state multiplier rows found in {resolved_path}.")
    return multipliers


def estimate_system_size(
    area_m2: float,
    panel_specs: dict[str, Any],
    packing_factor: float = 0.85,
    ghi_kwh_m2_day: float | None = None,
    performance_ratio: float = 0.80,
) -> dict[str, float | int | None]:
    """
    Layer 1: convert available area and panel specs into DC system size.

    GHI affects energy output, not nameplate capacity, so it is used only for
    the optional annual_energy_kwh estimate.
    """
    area_m2 = _require_positive(area_m2, "area_m2")
    packing_factor = _require_ratio(packing_factor, "packing_factor")
    performance_ratio = _require_ratio(performance_ratio, "performance_ratio")

    try:
        panel_length_m = _require_positive(float(panel_specs["length_m"]), "panel_specs.length_m")
        panel_width_m = _require_positive(float(panel_specs["width_m"]), "panel_specs.width_m")
        panel_power_w = _require_positive(float(panel_specs["STC_W"]), "panel_specs.STC_W")
    except KeyError as exc:
        raise ValueError(f"Missing panel spec: {exc.args[0]}") from exc

    panel_area_m2 = panel_length_m * panel_width_m
    usable_area_m2 = area_m2 * packing_factor
    n_panels = int(usable_area_m2 // panel_area_m2)
    capacity_kw_dc = (n_panels * panel_power_w) / 1000
    panel_efficiency = panel_power_w / (panel_area_m2 * 1000)

    annual_energy_kwh = None
    if ghi_kwh_m2_day is not None:
        ghi_kwh_m2_day = _require_positive(ghi_kwh_m2_day, "ghi_kwh_m2_day")
        annual_energy_kwh = capacity_kw_dc * ghi_kwh_m2_day * 365 * performance_ratio

    result = SystemSize(
        n_panels=n_panels,
        panel_area_m2=round(panel_area_m2, 4),
        usable_area_m2=round(usable_area_m2, 2),
        capacity_kw_dc=round(capacity_kw_dc, 2),
        panel_efficiency=round(panel_efficiency, 4),
        annual_energy_kwh=None if annual_energy_kwh is None else round(annual_energy_kwh, 2),
    )
    return result.__dict__


def estimate_base_cost(
    capacity_kw_dc: float,
    benchmarks_usd_per_w: dict[str, float] | None = None,
) -> dict[str, float | str]:
    """
    Layer 2: apply a size-tier benchmark in USD/W to estimate baseline capex.
    """
    capacity_kw_dc = _require_positive(capacity_kw_dc, "capacity_kw_dc")
    benchmarks = benchmarks_usd_per_w or load_atb_benchmarks()
    tier = _resolve_system_tier(capacity_kw_dc)

    if tier not in benchmarks:
        raise ValueError(f"Missing benchmark for tier '{tier}'.")

    benchmark_usd_per_w = _require_positive(benchmarks[tier], f"benchmarks_usd_per_w.{tier}")
    base_cost_usd = capacity_kw_dc * 1000 * benchmark_usd_per_w

    return {
        "system_tier": tier,
        "benchmark_usd_per_w": round(benchmark_usd_per_w, 4),
        "base_cost_usd": round(base_cost_usd, 2),
    }


def apply_regional_adjustment(
    base_cost_usd: float,
    state: str,
    state_cost_multipliers: dict[str, float] | None = None,
) -> dict[str, float | str]:
    """
    Layer 3: multiply base capex by a state-level cost multiplier.
    """
    base_cost_usd = _require_positive(base_cost_usd, "base_cost_usd")
    state = _normalize_state(state)
    multipliers = state_cost_multipliers or load_state_cost_multipliers()

    if state not in multipliers:
        raise ValueError(f"Missing state cost multiplier for '{state}'.")

    state_multiplier = _require_positive(multipliers[state], f"state_cost_multipliers.{state}")
    adjusted_cost_usd = base_cost_usd * state_multiplier

    return {
        "state": state,
        "state_cost_multiplier": round(state_multiplier, 4),
        "adjusted_cost_usd": round(adjusted_cost_usd, 2),
    }


def apply_incentives(
    adjusted_cost_usd: float,
    year: int,
    state_rebate_usd: float = 0.0,
    federal_itc_rate: float | None = None,
) -> dict[str, float]:
    """
    Layer 4: apply federal ITC and optional fixed-dollar state rebate.
    """
    adjusted_cost_usd = _require_positive(adjusted_cost_usd, "adjusted_cost_usd")
    state_rebate_usd = float(state_rebate_usd)
    if state_rebate_usd < 0:
        raise ValueError("state_rebate_usd cannot be negative.")

    if federal_itc_rate is None:
        federal_itc_rate = FEDERAL_ITC.get(year, 0.10)
    federal_itc_rate = _require_ratio(federal_itc_rate, "federal_itc_rate")

    federal_itc_amount = adjusted_cost_usd * federal_itc_rate
    net_cost_usd = max(adjusted_cost_usd - federal_itc_amount - state_rebate_usd, 0.0)

    return {
        "federal_itc_rate": round(federal_itc_rate, 4),
        "federal_itc_amount_usd": round(federal_itc_amount, 2),
        "state_rebate_usd": round(state_rebate_usd, 2),
        "net_cost_usd": round(net_cost_usd, 2),
    }


def estimate_solar_project_cost(
    *,
    area_m2: float,
    panel_specs: dict[str, Any],
    state: str,
    year: int = 2026,
    ghi_kwh_m2_day: float | None = None,
    packing_factor: float = 0.85,
    performance_ratio: float = 0.80,
    state_rebate_usd: float = 0.0,
    benchmarks_usd_per_w: dict[str, float] | None = None,
    state_cost_multipliers: dict[str, float] | None = None,
    federal_itc_rate: float | None = None,
) -> dict[str, Any]:
    """
    Execute the full 4-layer cost pipeline.
    """
    system_size = estimate_system_size(
        area_m2=area_m2,
        panel_specs=panel_specs,
        packing_factor=packing_factor,
        ghi_kwh_m2_day=ghi_kwh_m2_day,
        performance_ratio=performance_ratio,
    )
    base_cost = estimate_base_cost(
        capacity_kw_dc=float(system_size["capacity_kw_dc"]),
        benchmarks_usd_per_w=benchmarks_usd_per_w,
    )
    regional_cost = apply_regional_adjustment(
        base_cost_usd=float(base_cost["base_cost_usd"]),
        state=state,
        state_cost_multipliers=state_cost_multipliers,
    )
    incentives = apply_incentives(
        adjusted_cost_usd=float(regional_cost["adjusted_cost_usd"]),
        year=year,
        state_rebate_usd=state_rebate_usd,
        federal_itc_rate=federal_itc_rate,
    )

    return {
        "inputs": {
            "area_m2": area_m2,
            "state": _normalize_state(state),
            "year": year,
            "ghi_kwh_m2_day": ghi_kwh_m2_day,
            "packing_factor": packing_factor,
            "performance_ratio": performance_ratio,
            "benchmarks_source": str(ATB_BENCHMARKS_CSV),
            "state_multipliers_source": str(STATE_COST_MULTIPLIERS_CSV),
        },
        "layer_1_system_size": system_size,
        "layer_2_base_cost": base_cost,
        "layer_3_regional_adjustment": regional_cost,
        "layer_4_incentives": incentives,
    }


def example_estimate_solar_project_cost() -> dict[str, Any]:
    """
    Small local test helper so you can verify the estimator returns output.
    Run: python backend/cost/cost.py
    """
    return estimate_solar_project_cost(
        area_m2=120,
        panel_specs={"length_m": 1.72, "width_m": 1.13, "STC_W": 440},
        state="IN",
        year=2026,
        ghi_kwh_m2_day=4.5,
        state_rebate_usd=1500,
    )


if __name__ == "__main__":
    print(json.dumps(example_estimate_solar_project_cost(), indent=2))
