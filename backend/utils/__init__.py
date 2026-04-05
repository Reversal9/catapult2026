"""
Backend utility modules for common operations and validation.

Provides:
- helpers: General utility functions
- validators: Data validation and unit conversion
"""

from .helpers import (
    clamp,
    format_decimal,
    log_debug,
    merge_dicts,
    normalize_degrees,
    safe_divide,
    safe_get_nested,
)
from .validators import (
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    kilowatt_hours_to_megawatt_hours,
    kilowatts_to_watts,
    kwh_per_m2_per_day_to_per_year,
    kwh_per_m2_per_year_to_per_day,
    megawatt_hours_to_kilowatt_hours,
    square_kilometers_to_square_meters,
    square_meters_to_square_kilometers,
    validate_coordinate_pair,
    validate_latitude,
    validate_longitude,
    validate_min_list_length,
    validate_non_empty_list,
    validate_panel_azimuth,
    validate_panel_efficiency,
    validate_panel_tilt,
    validate_packing_efficiency,
    validate_performance_ratio,
    validate_positive,
    validate_range,
)

__all__ = [
    "clamp",
    "format_decimal",
    "log_debug",
    "merge_dicts",
    "normalize_degrees",
    "safe_divide",
    "safe_get_nested",
    "validate_coordinate_pair",
    "validate_latitude",
    "validate_longitude",
    "validate_min_list_length",
    "validate_negative",
    "validate_non_empty_list",
    "validate_panel_azimuth",
    "validate_panel_efficiency",
    "validate_panel_tilt",
    "validate_packing_efficiency",
    "validate_performance_ratio",
    "validate_positive",
    "validate_range",
    "celsius_to_fahrenheit",
    "fahrenheit_to_celsius",
    "kilowatt_hours_to_megawatt_hours",
    "kilowatts_to_watts",
    "kwh_per_m2_per_year_to_per_day",
    "megawatt_hours_to_kilowatt_hours",
    "square_kilometers_to_square_meters",
    "square_meters_to_square_kilometers",
]
