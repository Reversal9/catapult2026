"""
Regex-based extractors for solar panel spec fields.
All functions accept a raw text blob and return typed Python values.
"""
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_float(pattern: str, text: str, flags: int = re.IGNORECASE) -> Optional[float]:
    m = re.search(pattern, text, flags)
    if m:
        try:
            return float(m.group(1).replace("−", "-").replace(",", "."))
        except ValueError:
            pass
    return None


def _minus(s: str) -> float:
    """Normalise unicode minus / en-dash to ASCII minus before float()."""
    return float(s.replace("−", "-").replace("–", "-").replace(",", "."))


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

def extract_dimensions(text: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (length_mm, width_mm, depth_mm). All three or None."""
    sep = r"\s*[xX×*]\s*"
    num = r"(\d{3,4}(?:\.\d+)?)"
    # e.g. "1665 x 991 x 38 mm" or "1665×991×38"
    m = re.search(rf"{num}{sep}{num}{sep}{num}\s*(?:mm)?", text)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return None, None, None


# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------

def extract_power(text: str) -> Optional[float]:
    """Peak power in Watts (STC)."""
    # Prefer labelled rows
    for label in [
        r"Maximum Power[^0-9]{0,30}",
        r"Rated Power[^0-9]{0,20}",
        r"Nominal Power[^0-9]{0,20}",
        r"Peak Power[^0-9]{0,20}",
        r"Pmax[^0-9]{0,10}",
    ]:
        v = _first_float(rf"{label}(\d{{3,4}}(?:\.\d+)?)\s*W", text)
        if v:
            return v
    # Bare "NNN Wp"
    v = _first_float(r"(\d{3,4}(?:\.\d+)?)\s*Wp\b", text)
    if v:
        return v
    return None


# ---------------------------------------------------------------------------
# Efficiency
# ---------------------------------------------------------------------------

def extract_efficiency(text: str) -> Optional[float]:
    for label in [r"Module Efficiency[^0-9]{0,20}", r"Efficiency[^0-9]{0,20}"]:
        v = _first_float(rf"{label}(\d{{1,2}}(?:\.\d+)?)\s*%", text)
        if v and 5.0 < v < 35.0:
            return v
    return None


# ---------------------------------------------------------------------------
# Electrical — voltages & currents
# ---------------------------------------------------------------------------

def extract_voc(text: str) -> Optional[float]:
    return _first_float(
        r"(?:Open.?Circuit Voltage|Voc)\D{0,10}(\d{2,3}(?:\.\d+)?)\s*V", text
    )


def extract_vmp(text: str) -> Optional[float]:
    return _first_float(
        r"(?:Max(?:imum)? Power Voltage|Vmpp?|Vmp)\D{0,10}(\d{2,3}(?:\.\d+)?)\s*V", text
    )


def extract_isc(text: str) -> Optional[float]:
    return _first_float(
        r"(?:Short.?Circuit Current|Isc)\D{0,10}(\d{1,2}(?:\.\d+)?)\s*A", text
    )


def extract_imp(text: str) -> Optional[float]:
    return _first_float(
        r"(?:Max(?:imum)? Power Current|Impp?|Imp)\D{0,10}(\d{1,2}(?:\.\d+)?)\s*A", text
    )


# ---------------------------------------------------------------------------
# Weight
# ---------------------------------------------------------------------------

def extract_weight(text: str) -> Optional[float]:
    v = _first_float(r"(?:Weight|Mass)\D{0,10}(\d{1,3}(?:\.\d+)?)\s*kg", text)
    if v and 5.0 < v < 100.0:
        return v
    return None


# ---------------------------------------------------------------------------
# Temperature coefficient
# ---------------------------------------------------------------------------

def extract_temp_coeff(text: str) -> Optional[float]:
    # e.g. "Temp. Coefficient of Pmax: -0.38 %/°C"
    m = re.search(
        r"(?:Temp(?:erature)?\s*Coeff(?:icient)?[^P]{0,30}Pmax"
        r"|Pmax[^T]{0,30}Temp(?:erature)?\s*Coeff(?:icient)?)"
        r"\D{0,10}([-−]?\d+(?:\.\d+)?)\s*%",
        text, re.IGNORECASE,
    )
    if m:
        v = _minus(m.group(1))
        if -2.0 < v < 0.0:
            return v
    return None


# ---------------------------------------------------------------------------
# Operating temperature range
# ---------------------------------------------------------------------------

def extract_operating_temp(text: str) -> tuple[Optional[float], Optional[float]]:
    m = re.search(
        r"(?:Operating Temp(?:erature)?)\D{0,10}"
        r"([-−]?\d+)\s*°?C?\s*(?:~|to|—|–|-)\s*([-+−]?\d+)\s*°?C",
        text, re.IGNORECASE,
    )
    if m:
        return _minus(m.group(1)), _minus(m.group(2))
    return None, None


# ---------------------------------------------------------------------------
# Max system voltage
# ---------------------------------------------------------------------------

def extract_max_voltage(text: str) -> Optional[float]:
    return _first_float(
        r"(?:Max(?:imum)? System Voltage|System Voltage)\D{0,10}(\d{3,4}(?:\.\d+)?)\s*V",
        text,
    )


# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------

_CERT_PATTERNS = [
    r"UL\s*\d{3,5}",
    r"IEC\s*\d{5}(?:[:\-]\d+)?",
    r"EN\s*\d{5}",
    r"ISO\s*\d{4,5}",
    r"MCS\b",
    r"CE\b",
    r"TÜV\b",
    r"TUV\b",
    r"CEC\b",
    r"CQC\b",
    r"PID\b",
]


def extract_certifications(text: str) -> list[str]:
    found: list[str] = []
    for p in _CERT_PATTERNS:
        for m in re.finditer(p, text, re.IGNORECASE):
            cert = m.group(0).strip()
            if cert.upper() not in {c.upper() for c in found}:
                found.append(cert)
    return found


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------

def extract_price(text: str) -> tuple[Optional[float], Optional[float]]:
    """Return (price_usd, price_per_watt_usd)."""
    # $/W pattern first
    ppw: Optional[float] = None
    m = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)\s*/\s*[Ww]\b", text)
    if m:
        ppw = float(m.group(1))

    # All $ amounts — pick the smallest credible panel price (< $2000)
    amounts = [
        float(m.group(1))
        for m in re.finditer(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
        if 10 <= float(m.group(1)) <= 2000
    ]
    price: Optional[float] = min(amounts) if amounts else None

    return price, ppw


# ---------------------------------------------------------------------------
# All-in-one
# ---------------------------------------------------------------------------

def extract_all(text: str) -> dict:
    """Run every extractor on `text`, return a flat dict matching PanelSpec fields."""
    l, w, d = extract_dimensions(text)
    t_min, t_max = extract_operating_temp(text)
    price, ppw = extract_price(text)
    return {
        "dimensions_mm": {"length_mm": l, "width_mm": w, "depth_mm": d},
        "weight_kg": extract_weight(text),
        "power_stc_w": extract_power(text),
        "efficiency_pct": extract_efficiency(text),
        "voc_v": extract_voc(text),
        "vmp_v": extract_vmp(text),
        "isc_a": extract_isc(text),
        "imp_a": extract_imp(text),
        "temp_coeff_pmax_pct_per_c": extract_temp_coeff(text),
        "operating_temp_c": {"min_c": t_min, "max_c": t_max},
        "max_system_voltage_v": extract_max_voltage(text),
        "certifications": extract_certifications(text),
        "price_usd": price,
        "price_per_watt_usd": ppw,
    }
