from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from asset_analysis import analyze_asset_polygon
from schemas import AssetAnalysisRequest, Coordinate


class AssetAnalysisTests(unittest.TestCase):
    def test_solar_asset_analysis_uses_packed_project_estimate(self) -> None:
        request = AssetAnalysisRequest(
            asset_type="solar",
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ],
        )

        class StubPredictor:
            model_name = "habakkuk"

            def predict(self, **kwargs):
                return 321_000.0, {
                    "climate_annual_cloud_cover_pct": 18.0,
                    "climate_annual_temperature_c": 24.0,
                }

        with patch(
            "asset_analysis.fetch_daily_solar_history",
            return_value=(
                [
                    {
                        "date": "2025-01-01",
                        "radiation_kwh_m2": 5.0,
                        "sunshine_seconds": 26000,
                    },
                    {
                        "date": "2025-01-02",
                        "radiation_kwh_m2": 5.5,
                        "sunshine_seconds": 28000,
                    },
                ],
                "stub-weather",
                "2025-01-01",
                "2025-12-31",
            ),
        ), patch("solar_project.get_predictor", return_value=StubPredictor()):
            result = analyze_asset_polygon(request)

        self.assertEqual(result.asset_type, "solar")
        self.assertEqual(result.metadata["model_source"], "habakkuk")
        self.assertGreater(result.asset_count or 0, 0)
        self.assertEqual(result.estimated_annual_output_kwh, 321_000.0)
        self.assertEqual(len(result.daily_generation_kwh), 2)

    def test_solar_asset_analysis_returns_daily_generation(self) -> None:
        request = AssetAnalysisRequest(
            asset_type="solar",
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ],
        )

        with patch(
            "asset_analysis.fetch_daily_solar_history",
            return_value=(
                [
                    {
                        "date": "2025-01-01",
                        "radiation_kwh_m2": 5.0,
                        "sunshine_seconds": 26000,
                    },
                    {
                        "date": "2025-01-02",
                        "radiation_kwh_m2": 5.5,
                        "sunshine_seconds": 28000,
                    },
                ],
                "stub-weather",
                "2025-01-01",
                "2025-12-31",
            ),
        ):
            result = analyze_asset_polygon(request)

        self.assertEqual(result.asset_type, "solar")
        self.assertEqual(result.weather_source, "stub-weather")
        self.assertEqual(len(result.daily_generation_kwh), 2)
        self.assertGreater(result.estimated_annual_output_kwh or 0, 0)

    def test_wind_asset_analysis_returns_turbine_summary(self) -> None:
        request = AssetAnalysisRequest(
            asset_type="wind",
            points=[
                Coordinate(lat=40.0, lon=-104.0),
                Coordinate(lat=40.0, lon=-103.95),
                Coordinate(lat=40.03, lon=-103.95),
                Coordinate(lat=40.03, lon=-104.0),
            ],
        )

        with patch(
            "asset_analysis.fetch_daily_wind_history",
            return_value=(
                [
                    {"date": "2025-01-01", "wind_speed_mps": 7.2},
                    {"date": "2025-01-02", "wind_speed_mps": 7.4},
                ],
                "stub-weather",
                "2025-01-01",
                "2025-12-31",
            ),
        ):
            result = analyze_asset_polygon(request)

        self.assertEqual(result.asset_type, "wind")
        self.assertGreater(result.asset_count or 0, 0)
        self.assertGreater(result.installed_capacity_kw or 0, 0)
        self.assertGreater(result.estimated_annual_output_kwh or 0, 0)

    def test_data_center_analysis_has_no_generation_trend(self) -> None:
        request = AssetAnalysisRequest(
            asset_type="data_center",
            points=[
                Coordinate(lat=35.0, lon=-97.0),
                Coordinate(lat=35.0, lon=-96.99),
                Coordinate(lat=35.01, lon=-96.99),
                Coordinate(lat=35.01, lon=-97.0),
            ],
        )

        result = analyze_asset_polygon(request)

        self.assertEqual(result.asset_type, "data_center")
        self.assertEqual(result.daily_generation_kwh, [])
        self.assertIn("consume power", result.metadata["note"])
