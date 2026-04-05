from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schemas import Coordinate, SolarAnalysisRequest
from solar_analysis import analyze_solar_polygon


class SolarAnalysisTests(unittest.TestCase):
    def test_analyze_solar_polygon_reports_habakkuk_when_predictor_loaded(self) -> None:
        request = SolarAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ]
        )

        class StubPredictor:
            model_name = "habakkuk"

            def predict(self, **kwargs):
                return 123_456.0, {
                    "climate_annual_cloud_cover_pct": 25.0,
                    "climate_annual_temperature_c": 22.0,
                }

        with patch(
            "solar_analysis.fetch_annual_solar_intensity",
            return_value=(1_850.0, "stub"),
        ), patch("solar_analysis.get_predictor", return_value=StubPredictor()):
            result = analyze_solar_polygon(request)

        self.assertEqual(result.model_source, "habakkuk")
        self.assertEqual(result.estimated_annual_output_kwh, 123_456.0)

    def test_analyze_solar_polygon_returns_expected_fields(self) -> None:
        request = SolarAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ]
        )

        with patch(
            "solar_analysis.fetch_annual_solar_intensity",
            return_value=(1_850.0, "stub"),
        ):
            result = analyze_solar_polygon(request)

        self.assertEqual(result.weather_source, "stub")
        self.assertGreater(result.panel_count, 0)
        self.assertGreater(result.installed_capacity_kw, 0)
        self.assertGreater(result.estimated_annual_output_kwh, 0)
        self.assertGreater(result.total_project_cost_usd, 0)
        self.assertTrue(result.suitable)

    def test_analyze_solar_polygon_marks_low_sunlight_as_unsuitable(self) -> None:
        request = SolarAnalysisRequest(
            points=[
                Coordinate(lat=47.0, lon=-120.0),
                Coordinate(lat=47.0, lon=-119.999),
                Coordinate(lat=47.001, lon=-119.999),
                Coordinate(lat=47.001, lon=-120.0),
            ]
        )

        with patch(
            "solar_analysis.fetch_annual_solar_intensity",
            return_value=(1_000.0, "stub"),
        ):
            result = analyze_solar_polygon(request)

        self.assertFalse(result.suitable)
        self.assertIn("threshold", result.suitability_reason.lower())

    def test_analyze_solar_polygon_falls_back_when_predictor_breaks(self) -> None:
        request = SolarAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ]
        )

        class BrokenPredictor:
            model_name = "habakkuk"

            def predict(self, **kwargs):
                raise RuntimeError("matrix shape mismatch")

        with patch(
            "solar_analysis.fetch_annual_solar_intensity",
            return_value=(1_850.0, "stub"),
        ), patch("solar_analysis.get_predictor", return_value=BrokenPredictor()):
            result = analyze_solar_polygon(request)

        self.assertEqual(result.model_source, "physics-fallback")
        self.assertGreater(result.estimated_annual_output_kwh, 0)
