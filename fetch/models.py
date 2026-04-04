from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class Dimensions:
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None


@dataclass
class TempRange:
    min_c: Optional[float] = None
    max_c: Optional[float] = None


@dataclass
class PanelSpec:
    model: str
    dimensions_mm: Dimensions = field(default_factory=Dimensions)
    weight_kg: Optional[float] = None
    power_stc_w: Optional[float] = None       # rated peak power at STC (1000 W/m², 25°C)
    efficiency_pct: Optional[float] = None
    voc_v: Optional[float] = None             # open-circuit voltage
    vmp_v: Optional[float] = None             # max-power voltage
    isc_a: Optional[float] = None             # short-circuit current
    imp_a: Optional[float] = None             # max-power current
    temp_coeff_pmax_pct_per_c: Optional[float] = None  # e.g. -0.38 %/°C
    operating_temp_c: TempRange = field(default_factory=TempRange)
    max_system_voltage_v: Optional[float] = None
    certifications: list = field(default_factory=list)
    price_usd: Optional[float] = None
    price_per_watt_usd: Optional[float] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None         # "enfsolar" | "pdf_datasheet" | "html_page"
    confidence: str = "low"

    # Fields used to compute confidence
    _CORE_FIELDS = [
        "weight_kg", "power_stc_w", "efficiency_pct",
        "voc_v", "vmp_v", "isc_a", "imp_a",
        "temp_coeff_pmax_pct_per_c", "max_system_voltage_v",
    ]

    def _compute_confidence(self) -> str:
        filled = sum(1 for f in self._CORE_FIELDS if getattr(self, f) is not None)
        filled += 1 if self.dimensions_mm.length_mm is not None else 0
        if filled >= 8:
            return "high"
        if filled >= 4:
            return "medium"
        return "low"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = self._compute_confidence()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
