from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from infrastructure_pipeline import (
    BuildingFootprint,
    ImageryRaster,
    RoadFeature,
    analyze_infrastructure_polygon,
)
from infrastructure.scoring import solar_candidate
from schemas import Coordinate, InfrastructureAnalysisRequest


class InfrastructurePipelineTests(unittest.TestCase):
    def test_solar_candidate_uses_shared_packed_project_estimate(self) -> None:
        cell = {
            "id": "cell-1",
            "center_lat": 33.0,
            "center_lon": -112.0,
            "polygon": [
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.99),
                Coordinate(lat=33.01, lon=-111.99),
                Coordinate(lat=33.01, lon=-112.0),
            ],
            "area_m2": 100_000.0,
            "rooftop_area_m2": 8_000.0,
            "open_land_area_m2": 30_000.0,
            "water_ratio": 0.0,
            "shading_factor": 0.08,
            "slope_deg": 2.5,
            "built_ratio": 0.12,
            "vegetation_ratio": 0.1,
        }

        class StubPredictor:
            model_name = "habakkuk"

            def predict(self, **kwargs):
                return 456_789.0, {
                    "climate_annual_cloud_cover_pct": 18.0,
                    "climate_annual_temperature_c": 24.0,
                }

        with patch("solar_project.get_predictor", return_value=StubPredictor()):
            candidate = solar_candidate(cell, 1)

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.metadata["model_source"], "habakkuk")
        self.assertGreater(candidate.metadata["panel_count"], 0)
        self.assertEqual(candidate.estimated_annual_output_kwh, 456_789.0)

    def test_request_defaults_prefer_free_imagery_and_live_terrain(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.99),
                Coordinate(lat=33.01, lon=-111.99),
            ]
        )

        self.assertEqual(request.imagery_provider, "usgs")
        self.assertEqual(request.segmentation_backend, "auto")
        self.assertEqual(request.terrain_provider, "opentopodata")

    def test_pipeline_returns_ranked_candidates(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.95),
                Coordinate(lat=33.03, lon=-111.95),
                Coordinate(lat=33.03, lon=-112.0),
            ],
            cell_size_m=500,
        )

        result = analyze_infrastructure_polygon(request)

        self.assertGreater(result.area_m2, 0)
        self.assertGreater(result.subdivisions_evaluated, 0)
        self.assertGreater(len(result.candidates), 0)
        self.assertIn(result.candidates[0].use_type, {"solar", "wind", "data_center"})

    def test_pipeline_rejects_self_intersecting_polygon(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                Coordinate(lat=0.0, lon=0.0),
                Coordinate(lat=1.0, lon=1.0),
                Coordinate(lat=0.0, lon=1.0),
                Coordinate(lat=1.0, lon=0.0),
            ],
            cell_size_m=400,
        )

        with self.assertRaises(ValueError):
            analyze_infrastructure_polygon(request)

    def test_pipeline_uses_live_imagery_and_osm_vectors_when_available(self) -> None:
        request = InfrastructureAnalysisRequest(
            points=[
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.99),
                Coordinate(lat=33.01, lon=-111.99),
                Coordinate(lat=33.01, lon=-112.0),
            ],
            cell_size_m=400,
            imagery_provider="mapbox",
        )

        imagery = ImageryRaster(
            provider="mapbox",
            source="mapbox-static-images:test-style",
            width=8,
            height=8,
            bbox=None,  # filled in by side effect below
            rows=[[(180, 182, 178, 255) for _ in range(8)] for _ in range(8)],
        )

        building = BuildingFootprint(
            polygon=[
                Coordinate(lat=33.0020, lon=-111.9986),
                Coordinate(lat=33.0020, lon=-111.9968),
                Coordinate(lat=33.0041, lon=-111.9968),
                Coordinate(lat=33.0041, lon=-111.9986),
                Coordinate(lat=33.0020, lon=-111.9986),
            ],
            bbox=None,  # filled in by side effect below
            area_m2=46_000.0,
        )
        road = RoadFeature(
            points=[
                Coordinate(lat=33.0015, lon=-111.9995),
                Coordinate(lat=33.0090, lon=-111.9995),
            ],
            highway_type="primary",
        )

        def fake_imagery_fetch(_provider, bbox):
            return (
                ImageryRaster(
                    provider=imagery.provider,
                    source=imagery.source,
                    width=imagery.width,
                    height=imagery.height,
                    bbox=bbox,
                    rows=imagery.rows,
                ),
                imagery.source,
                ["mock imagery"],
            )

        def fake_vector_fetch(bbox):
            live_building = BuildingFootprint(
                polygon=building.polygon,
                bbox=bbox.__class__(
                    min_lat=min(point.lat for point in building.polygon),
                    min_lon=min(point.lon for point in building.polygon),
                    max_lat=max(point.lat for point in building.polygon),
                    max_lon=max(point.lon for point in building.polygon),
                ),
                area_m2=building.area_m2,
            )
            return [live_building], [road], "osm-overpass", ["mock vectors"]

        with patch("infrastructure.pipeline.fetch_imagery_raster", side_effect=fake_imagery_fetch), patch(
            "infrastructure.pipeline.fetch_osm_vectors",
            side_effect=fake_vector_fetch,
        ):
            result = analyze_infrastructure_polygon(request)

        self.assertEqual(result.data_sources.imagery, "mapbox-static-images:test-style")
        self.assertEqual(result.data_sources.vector_data, "osm-overpass")
        self.assertGreater(len(result.candidates), 0)
        self.assertTrue(
            any(candidate.metadata.get("building_coverage_ratio", 0) > 0 for candidate in result.candidates)
        )
