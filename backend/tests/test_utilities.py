"""
Comprehensive tests for backend utilities and helper functions.

Tests coverage:
- helpers.py: clamp, log_debug, normalize_degrees, safe operations
- validators.py: coordinate validation, unit conversions, solar parameters
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from utils.helpers import (
    clamp,
    format_decimal,
    merge_dicts,
    normalize_degrees,
    safe_divide,
    safe_get_nested,
)
from utils.validators import (
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    kwh_per_m2_per_day_to_per_year,
    kwh_per_m2_per_year_to_per_day,
    square_kilometers_to_square_meters,
    square_meters_to_square_kilometers,
    validate_coordinate_pair,
    validate_latitude,
    validate_longitude,
    validate_non_empty_list,
    validate_panel_azimuth,
    validate_panel_efficiency,
    validate_panel_tilt,
    validate_packing_efficiency,
    validate_performance_ratio,
    validate_positive,
    validate_range,
)


class HelperFunctionTests(unittest.TestCase):
    """Test general utility functions."""

    def test_clamp_within_range(self):
        """Clamp should return value unchanged if within bounds."""
        self.assertEqual(clamp(50.0, 0.0, 100.0), 50.0)

    def test_clamp_below_minimum(self):
        """Clamp should return minimum if value below it."""
        self.assertEqual(clamp(-10.0, 0.0, 100.0), 0.0)

    def test_clamp_above_maximum(self):
        """Clamp should return maximum if value above it."""
        self.assertEqual(clamp(150.0, 0.0, 100.0), 100.0)

    def test_format_decimal_default_precision(self):
        """Format to default 2 decimal places."""
        self.assertEqual(format_decimal(3.14159), 3.14)

    def test_format_decimal_custom_precision(self):
        """Format to custom decimal places."""
        self.assertEqual(format_decimal(3.14159, decimals=4), 3.1416)

    def test_normalize_degrees_in_range(self):
        """Degrees already in range should return unchanged."""
        self.assertEqual(normalize_degrees(180.0), 180.0)

    def test_normalize_degrees_overflow(self):
        """Degrees > 360 should wrap around."""
        self.assertEqual(normalize_degrees(450.0), 90.0)

    def test_normalize_degrees_negative(self):
        """Negative degrees should wrap into positive range."""
        self.assertEqual(normalize_degrees(-90.0), 270.0)

    def test_safe_divide_normal(self):
        """Safe divide with non-zero denominator."""
        self.assertEqual(safe_divide(10.0, 2.0), 5.0)

    def test_safe_divide_by_zero(self):
        """Safe divide by zero returns default."""
        self.assertEqual(safe_divide(10.0, 0.0), 0.0)

    def test_safe_divide_custom_default(self):
        """Safe divide with custom default value."""
        self.assertEqual(safe_divide(10.0, 0.0, default=-1.0), -1.0)

    def test_safe_get_nested_simple(self):
        """Get value from simple dict path."""
        data = {"key": "value"}
        self.assertEqual(safe_get_nested(data, "key"), "value")

    def test_safe_get_nested_dot_notation(self):
        """Get nested value using dot notation."""
        data = {"outer": {"inner": 42}}
        self.assertEqual(safe_get_nested(data, "outer.inner"), 42)

    def test_safe_get_nested_missing_key(self):
        """Missing key returns default value."""
        data = {"key": "value"}
        self.assertEqual(safe_get_nested(data, "missing"), None)

    def test_safe_get_nested_list_index(self):
        """Get value from list using index notation."""
        data = {"list": [10, 20, 30]}
        self.assertEqual(safe_get_nested(data, "list.1"), 20)

    def test_merge_dicts_simple(self):
        """Merge two non-nested dicts."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = merge_dicts(base, override)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_merge_dicts_nested(self):
        """Merge nested dicts recursively."""
        base = {"level1": {"a": 1, "b": 2}}
        override = {"level1": {"b": 3}}
        result = merge_dicts(base, override)
        self.assertEqual(result, {"level1": {"a": 1, "b": 3}})


class CoordinateValidationTests(unittest.TestCase):
    """Test geographic coordinate validators."""

    def test_validate_latitude_valid(self):
        """Valid latitude should pass."""
        self.assertTrue(validate_latitude(45.0))
        self.assertTrue(validate_latitude(-45.0))
        self.assertTrue(validate_latitude(0.0))

    def test_validate_latitude_invalid_high(self):
        """Latitude > 90 should fail."""
        self.assertFalse(validate_latitude(91.0))

    def test_validate_latitude_invalid_low(self):
        """Latitude < -90 should fail."""
        self.assertFalse(validate_latitude(-91.0))

    def test_validate_longitude_valid(self):
        """Valid longitude should pass."""
        self.assertTrue(validate_longitude(180.0))
        self.assertTrue(validate_longitude(-180.0))

    def test_validate_longitude_invalid(self):
        """Longitude outside [-180, 180] should fail."""
        self.assertFalse(validate_longitude(181.0))

    def test_validate_coordinate_pair_valid(self):
        """Valid lat/lon pair should pass."""
        self.assertTrue(validate_coordinate_pair(40.0, -75.0))

    def test_validate_coordinate_pair_invalid_lat(self):
        """Invalid latitude in pair fails."""
        self.assertFalse(validate_coordinate_pair(91.0, -75.0))

    def test_validate_coordinate_pair_invalid_lon(self):
        """Invalid longitude in pair fails."""
        self.assertFalse(validate_coordinate_pair(40.0, 200.0))


class ValidationRangeTests(unittest.TestCase):
    """Test value range and constraint validators."""

    def test_validate_positive_valid(self):
        """Positive number should pass."""
        validate_positive(5.0, "test")  # Should not raise

    def test_validate_positive_zero_raises(self):
        """Zero should raise ValueError."""
        with self.assertRaises(ValueError):
            validate_positive(0.0, "test_value")

    def test_validate_positive_negative_raises(self):
        """Negative should raise ValueError."""
        with self.assertRaises(ValueError):
            validate_positive(-5.0, "test_value")

    def test_validate_range_within(self):
        """Value within range should pass."""
        validate_range(50.0, 0.0, 100.0, "test")  # Should not raise

    def test_validate_range_below_raises(self):
        """Value below min should raise."""
        with self.assertRaises(ValueError):
            validate_range(-10.0, 0.0, 100.0, "test")

    def test_validate_range_above_raises(self):
        """Value above max should raise."""
        with self.assertRaises(ValueError):
            validate_range(150.0, 0.0, 100.0, "test")

    def test_validate_non_empty_list_valid(self):
        """Non-empty list should pass."""
        validate_non_empty_list([1, 2, 3], "test")  # Should not raise

    def test_validate_non_empty_list_empty_raises(self):
        """Empty list should raise."""
        with self.assertRaises(ValueError):
            validate_non_empty_list([], "test_list")


class UnitConversionTests(unittest.TestCase):
    """Test unit conversion functions."""

    def test_square_meters_to_km(self):
        """Convert 1 million m² to 1 km²."""
        self.assertEqual(square_meters_to_square_kilometers(1_000_000.0), 1.0)

    def test_square_km_to_meters(self):
        """Convert 1 km² to 1 million m²."""
        self.assertEqual(square_kilometers_to_square_meters(1.0), 1_000_000.0)

    def test_kwh_per_m2_per_day_to_per_year(self):
        """Convert daily solar irradiance to annual."""
        result = kwh_per_m2_per_day_to_per_year(4.0)  # 4 kWh/m²/day
        self.assertAlmostEqual(result, 1460.0, places=1)  # ≈ 1460 kWh/m²/year

    def test_kwh_per_m2_per_year_to_per_day(self):
        """Convert annual solar irradiance to daily."""
        result = kwh_per_m2_per_year_to_per_day(1460.0)  # 1460 kWh/m²/year
        self.assertAlmostEqual(result, 4.0, places=2)  # ≈ 4 kWh/m²/day

    def test_celsius_to_fahrenheit(self):
        """Convert 0°C to 32°F."""
        self.assertEqual(celsius_to_fahrenheit(0.0), 32.0)

    def test_celsius_to_fahrenheit_freezing(self):
        """Convert 100°C to 212°F."""
        self.assertEqual(celsius_to_fahrenheit(100.0), 212.0)

    def test_fahrenheit_to_celsius(self):
        """Convert 32°F to 0°C."""
        self.assertEqual(fahrenheit_to_celsius(32.0), 0.0)


class SolarParameterValidationTests(unittest.TestCase):
    """Test solar-specific parameter validators."""

    def test_validate_panel_efficiency_valid(self):
        """Efficiency of 20% should pass."""
        validate_panel_efficiency(0.20)  # Should not raise

    def test_validate_panel_efficiency_too_high_raises(self):
        """Efficiency > 99% should raise."""
        with self.assertRaises(ValueError):
            validate_panel_efficiency(1.0)

    def test_validate_panel_tilt_valid_values(self):
        """Tilt values 0-90° should pass."""
        validate_panel_tilt(0.0)  # Should not raise
        validate_panel_tilt(45.0)  # Should not raise
        validate_panel_tilt(90.0)  # Should not raise

    def test_validate_panel_tilt_negative_raises(self):
        """Negative tilt should raise."""
        with self.assertRaises(ValueError):
            validate_panel_tilt(-10.0)

    def test_validate_panel_azimuth_valid_values(self):
        """Azimuth values 0-360° should pass."""
        validate_panel_azimuth(0.0)  # Should not raise
        validate_panel_azimuth(180.0)  # True south
        validate_panel_azimuth(360.0)  # Should not raise

    def test_validate_panel_azimuth_out_of_range_raises(self):
        """Azimuth > 360° should raise."""
        with self.assertRaises(ValueError):
            validate_panel_azimuth(361.0)

    def test_validate_performance_ratio_valid(self):
        """PR of 80% should pass."""
        validate_performance_ratio(0.8)  # Should not raise

    def test_validate_performance_ratio_invalid_raises(self):
        """PR > 100% should raise."""
        with self.assertRaises(ValueError):
            validate_performance_ratio(1.1)

    def test_validate_packing_efficiency_valid(self):
        """Packing of 75% should pass."""
        validate_packing_efficiency(0.75)  # Should not raise

    def test_validate_packing_efficiency_invalid_raises(self):
        """Packing > 100% should raise."""
        with self.assertRaises(ValueError):
            validate_packing_efficiency(1.5)


if __name__ == "__main__":
    unittest.main()
