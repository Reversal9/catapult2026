"""
General utility functions for solar and infrastructure analysis.

This module provides reusable helper functions for:
- Value normalization and clamping
- Logging structured data
- HTTP error handling
- Data validation
"""

from __future__ import annotations

import json
import logging
from typing import Any


LOGGER = logging.getLogger("uvicorn.error")


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Clamp a value between min and max bounds.
    
    Args:
        value: The value to clamp
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        The clamped value within [min_value, max_value]
    """
    return max(min_value, min(max_value, value))


def log_debug(tag: str, payload: dict[str, Any]) -> None:
    """
    Log structured debug information with a tag for filtering.
    
    Args:
        tag: Identifier tag for categorizing log entries
        payload: Dictionary of debug data to log as JSON
    """
    LOGGER.info("[%s] %s", tag, json.dumps(payload, sort_keys=True))


def normalize_degrees(degrees: float, min_deg: float = 0.0, max_deg: float = 360.0) -> float:
    """
    Normalize degrees to a range (default 0-360).
    
    Args:
        degrees: Degree value to normalize
        min_deg: Minimum degree value (default 0)
        max_deg: Maximum degree value (default 360)
        
    Returns:
        Normalized degree value
    """
    range_deg = max_deg - min_deg
    normalized = ((degrees - min_deg) % range_deg) + min_deg
    return normalized


def format_decimal(value: float, decimals: int = 2) -> float:
    """
    Round a float to a specific number of decimal places.
    
    Args:
        value: Value to round
        decimals: Number of decimal places
        
    Returns:
        Rounded float value
    """
    return round(value, decimals)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.
    
    Args:
        numerator: Dividend
        denominator: Divisor
        default: Value to return if denominator is zero
        
    Returns:
        Result of division or default value
    """
    if denominator == 0:
        return default
    return numerator / denominator


def safe_get_nested(data: dict, path: str, default: Any = None) -> Any:
    """
    Safely extract a nested value from a dictionary using dot notation.
    
    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., "layer.0.value")
        default: Value to return if path not found
        
    Returns:
        Value at path or default
    """
    keys = path.split(".")
    current = data
    try:
        for key in keys:
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, (list, tuple)):
                current = current[int(key)]
            else:
                return default
        return current
    except (KeyError, IndexError, TypeError, ValueError):
        return default


def merge_dicts(base: dict, override: dict) -> dict:
    """
    Recursively merge two dictionaries, with override values taking precedence.
    
    Args:
        base: Base dictionary
        override: Dictionary with values to override
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
