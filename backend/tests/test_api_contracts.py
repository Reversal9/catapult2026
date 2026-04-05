from __future__ import annotations

import sys
from pathlib import Path
import unittest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schemas import (
    AssetAnalysisRequest,
    InfrastructureAnalysisRequest,
    SolarAnalysisRequest,
)


class ApiContractTests(unittest.TestCase):
    def test_solar_request_defaults_are_sane(self) -> None:
        request = SolarAnalysisRequest(
            points=[
                {"lat": 33.0, "lon": -112.0},
                {"lat": 33.0, "lon": -111.999},
                {"lat": 33.001, "lon": -111.999},
            ]
        )

        self.assertGreater(request.panel_area_m2, 0)
        self.assertGreater(request.panel_rating_w, 0)
        self.assertIsNone(request.state)

    def test_asset_request_accepts_all_types(self) -> None:
        for asset_type in ["solar", "wind", "data_center"]:
            request = AssetAnalysisRequest(
                asset_type=asset_type,
                points=[
                    {"lat": 35.0, "lon": -97.0},
                    {"lat": 35.0, "lon": -96.99},
                    {"lat": 35.01, "lon": -96.99},
                ],
            )
            self.assertEqual(request.asset_type, asset_type)

    def test_infrastructure_defaults_include_all_use_types(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                {"lat": 33.0, "lon": -112.0},
                {"lat": 33.0, "lon": -111.99},
                {"lat": 33.01, "lon": -111.99},
            ]
        )

        self.assertEqual(request.imagery_provider, "usgs")
        self.assertEqual(request.allowed_use_types, ["solar", "wind", "data_center"])
