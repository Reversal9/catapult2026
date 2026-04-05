from __future__ import annotations

import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import asset_analyze, health, infrastructure_analyze, root, solar_analyze
from schemas import (
    AssetAnalysisRequest,
    Coordinate,
    InfrastructureAnalysisRequest,
    SolarAnalysisRequest,
)


class MainApiTests(unittest.TestCase):
    def test_root_health_endpoint(self) -> None:
        response = root()

        self.assertIn("running", response["message"].lower())

    def test_health_reports_model_status(self) -> None:
        response = health()

        self.assertEqual(response["status"], "ok")
        self.assertIn("model", response)

    def test_solar_analyze_endpoint(self) -> None:
        request = SolarAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ]
        )

        response = solar_analyze(request)

        self.assertGreater(response.area_m2, 0)
        self.assertIn("model_source", response.model_dump())

    def test_asset_analyze_endpoint(self) -> None:
        request = AssetAnalysisRequest(
            asset_type="data_center",
            points=[
                Coordinate(lat=35.0, lon=-97.0),
                Coordinate(lat=35.0, lon=-96.99),
                Coordinate(lat=35.01, lon=-96.99),
                Coordinate(lat=35.01, lon=-97.0),
            ],
        )

        response = asset_analyze(request)

        self.assertEqual(response.asset_type, "data_center")
        self.assertIn("metadata", response.model_dump())

    def test_infrastructure_analyze_endpoint(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.95),
                Coordinate(lat=33.03, lon=-111.95),
                Coordinate(lat=33.03, lon=-112.0),
            ],
            cell_size_m=500,
            imagery_provider="none",
            segmentation_backend="auto",
            terrain_provider="opentopodata",
            include_debug_layers=False,
            solar_spec={
                "panel_area_m2": 2.0,
                "panel_rating_w": 420.0,
                "panel_cost_usd": 260.0,
                "construction_cost_per_m2_usd": 140.0,
                "packing_efficiency": 0.75,
                "performance_ratio": 0.8,
                "sunlight_threshold_kwh_m2_yr": 1400.0,
            },
            allowed_use_types=["solar", "wind", "data_center"],
        )

        response = infrastructure_analyze(request)

        self.assertGreaterEqual(len(response.candidates), 0)
        self.assertIn("data_sources", response.model_dump())

    def test_infrastructure_rejects_bad_polygon(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                Coordinate(lat=0.0, lon=0.0),
                Coordinate(lat=1.0, lon=1.0),
                Coordinate(lat=0.0, lon=1.0),
                Coordinate(lat=1.0, lon=0.0),
            ],
            cell_size_m=400,
        )

        with self.assertRaises(Exception) as context:
            infrastructure_analyze(request)

        self.assertIn("400", str(context.exception))
