"""
Data validation and type conversion utilities.

This module provides functions for:
- Validating geographic coordinates
- Checking numerical ranges and constraints
- Converting units (area, energy, temperature, etc.)
- Validation of solar/wind parameters
"""

from __future__ import annotations

import re
from typing import Any


def validate_latitude(lat: float) -> bool:
    """
    Validate if a value is a valid latitude (-90 to 90 degrees).
    
    Args:
        lat: Latitude value to validate
        
    Returns:
        True if valid latitude, False otherwise
    """
    return isinstance(lat, (int, float)) and -90 <= lat <= 90


def validate_longitude(lon: float) -> bool:
    """
    Validate if a value is a valid longitude (-180 to 180 degrees).
    
    Args:
        lon: Longitude value to validate
        
    Returns:
        True if valid longitude, False otherwise
    """
    return isinstance(lon, (int, float)) and -180 <= lon <= 180


def validate_coordinate_pair(lat: float, lon: float) -> bool:
    """
    Validate a complete lat/lon coordinate pair.
    
    Args:
        lat: Latitude value
        lon: Longitude value
        
    Returns:
        True if both coordinates are valid
    """
    return validate_latitude(lat) and validate_longitude(lon)


def validate_positive(value: float, name: str = "value") -> None:
    """
    Validate that a value is positive, raising ValueError if not.
    
    Args:
        value: Value to validate
        name: Name of value for error message
        
    Raises:
        ValueError: If value is not positive
    """
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def validate_range(value: float, min_val: float, max_val: float, name: str = "value") -> None:
    """
    Validate that a value is within a range, raising ValueError if not.
    
    Args:
        value: Value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        name: Name of value for error message
        
    Raises:
        ValueError: If value is outside range
    """
    if not min_val <= value <= max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {value}")


def validate_non_empty_list(lst: list, name: str = "list") -> None:
    """
    Validate that a list is not empty.
    
    Args:
        lst: List to validate
        name: Name of list for error message
        
    Raises:
        ValueError: If list is empty
    """
    if not lst or len(lst) == 0:
        raise ValueError(f"{name} cannot be empty")


def validate_min_list_length(lst: list, min_length: int, name: str = "list") -> None:
    """
    Validate that a list has at least a minimum number of elements.
    
    Args:
        lst: List to validate
        min_length: Minimum required length
        name: Name of list for error message
        
    Raises:
        ValueError: If list is too short
    """
    if len(lst) < min_length:
        raise ValueError(f"{name} must have at least {min_length} items, got {len(lst)}")


# Unit conversion functions

def square_meters_to_square_kilometers(m2: float) -> float:
    """Convert square meters to square kilometers."""
    return m2 / 1_000_000.0


def square_kilometers_to_square_meters(km2: float) -> float:
    """Convert square kilometers to square meters."""
    return km2 * 1_000_000.0


def kilowatts_to_watts(kw: float) -> float:
    """Convert kilowatts to watts."""
    return kw * 1_000.0


def watts_to_kilowatts(w: float) -> float:
    """Convert watts to kilowatts."""
    return w / 1_000.0


def kilowatt_hours_to_megawatt_hours(kwh: float) -> float:
    """Convert kilowatt-hours to megawatt-hours."""
    return kwh / 1_000.0


def megawatt_hours_to_kilowatt_hours(mwh: float) -> float:
    """Convert megawatt-hours to kilowatt-hours."""
    return mwh * 1_000.0


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (celsius * 9 / 5) + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9


def kwh_per_m2_per_year_to_per_day(annual: float) -> float:
    """Convert annual kWh/m²/year to daily average kWh/m²/day."""
    return annual / 365.0


def kwh_per_m2_per_day_to_per_year(daily: float) -> float:
    """Convert daily kWh/m²/day to annual kWh/m²/year."""
    return daily * 365.0


# Solar parameter validators

def validate_panel_efficiency(efficiency: float) -> None:
    """
    Validate solar panel efficiency percentage (0-99%).
    
    Args:
        efficiency: Panel efficiency as decimal (0.1 = 10%)
        
    Raises:
        ValueError: If efficiency is out of valid range
    """
    validate_range(efficiency, 0.0, 0.99, "Panel efficiency")


def validate_panel_tilt(tilt_deg: float) -> None:
    """
    Validate solar panel tilt angle (0-90 degrees).
    
    Args:
        tilt_deg: Tilt angle in degrees
        
    Raises:
        ValueError: If tilt is out of valid range
    """
    validate_range(tilt_deg, 0.0, 90.0, "Panel tilt angle")


def validate_panel_azimuth(azimuth_deg: float) -> None:
    """
    Validate solar panel azimuth angle (0-360 degrees).
    
    Args:
        azimuth_deg: Azimuth angle in degrees
        
    Raises:
        ValueError: If azimuth is out of valid range
    """
    validate_range(azimuth_deg, 0.0, 360.0, "Panel azimuth angle")


def validate_performance_ratio(pr: float) -> None:
    """
    Validate performance ratio (0-100%).
    
    Args:
        pr: Performance ratio as decimal (0.8 = 80%)
        
    Raises:
        ValueError: If PR is out of valid range
    """
    validate_range(pr, 0.0, 1.0, "Performance ratio")


def validate_packing_efficiency(packing: float) -> None:
    """
    Validate packing efficiency (0-100%).
    
    Args:
        packing: Packing efficiency as decimal (0.75 = 75%)
        
    Raises:
        ValueError: If packing is out of valid range
    """
    validate_range(packing, 0.0, 1.0, "Packing efficiency")
