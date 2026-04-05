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
    WaterFeature,
    analyze_infrastructure_polygon,
)
from infrastructure.pipeline import _merge_solar_candidates
from infrastructure.scoring import solar_candidate, wind_candidate
from schemas import BoundingBox, CandidateRegion, Coordinate, InfrastructureAnalysisRequest


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

    def test_solar_candidate_prefers_building_rooftops_when_live_buildings_exist(self) -> None:
        cell = {
            "id": "cell-roof",
            "center_lat": 33.0,
            "center_lon": -112.0,
            "polygon": [
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.996),
                Coordinate(lat=33.004, lon=-111.996),
                Coordinate(lat=33.004, lon=-112.0),
            ],
            "area_m2": 60_000.0,
            "rooftop_area_m2": 240.0,
            "open_land_area_m2": 1_000.0,
            "water_ratio": 0.0,
            "shading_factor": 0.05,
            "slope_deg": 1.8,
            "built_ratio": 0.12,
            "vegetation_ratio": 0.1,
            "unobstructed_ratio": 0.92,
            "water_features": [],
        }
        buildings = [
            BuildingFootprint(
                polygon=[
                    Coordinate(lat=33.0006, lon=-111.9996),
                    Coordinate(lat=33.0006, lon=-111.9988),
                    Coordinate(lat=33.0012, lon=-111.9988),
                    Coordinate(lat=33.0012, lon=-111.9996),
                    Coordinate(lat=33.0006, lon=-111.9996),
                ],
                bbox=BoundingBox(
                    min_lat=33.0006,
                    min_lon=-111.9996,
                    max_lat=33.0012,
                    max_lon=-111.9988,
                ),
                area_m2=120.0,
            ),
            BuildingFootprint(
                polygon=[
                    Coordinate(lat=33.0021, lon=-111.9983),
                    Coordinate(lat=33.0021, lon=-111.9973),
                    Coordinate(lat=33.0029, lon=-111.9973),
                    Coordinate(lat=33.0029, lon=-111.9983),
                    Coordinate(lat=33.0021, lon=-111.9983),
                ],
                bbox=BoundingBox(
                    min_lat=33.0021,
                    min_lon=-111.9983,
                    max_lat=33.0029,
                    max_lon=-111.9973,
                ),
                area_m2=150.0,
            ),
        ]

        class StubPredictor:
            model_name = "habakkuk"

            def predict(self, **kwargs):
                return 34_500.0, {
                    "climate_annual_cloud_cover_pct": 16.0,
                    "climate_annual_temperature_c": 23.0,
                }

        with patch("solar_project.get_predictor", return_value=StubPredictor()):
            candidate = solar_candidate(cell, 7, buildings=buildings, roads=[])

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.metadata["validity_source"], "rooftop_buildings")
        self.assertEqual(len(candidate.metadata["valid_region_polygons"]), 2)
        self.assertGreaterEqual(candidate.metadata["panel_count"], 8)

    def test_rooftop_solar_panel_count_matches_rendered_layout_when_small(self) -> None:
        cell = {
            "id": "cell-roof-small",
            "center_lat": 33.0,
            "center_lon": -112.0,
            "polygon": [
                Coordinate(lat=33.0, lon=-112.0),
                Coordinate(lat=33.0, lon=-111.999),
                Coordinate(lat=33.001, lon=-111.999),
                Coordinate(lat=33.001, lon=-112.0),
            ],
            "area_m2": 10_000.0,
            "rooftop_area_m2": 220.0,
            "open_land_area_m2": 200.0,
            "water_ratio": 0.0,
            "shading_factor": 0.03,
            "slope_deg": 1.0,
            "built_ratio": 0.2,
            "vegetation_ratio": 0.05,
            "unobstructed_ratio": 0.96,
            "water_features": [],
        }
        buildings = [
            BuildingFootprint(
                polygon=[
                    Coordinate(lat=33.0002, lon=-111.9998),
                    Coordinate(lat=33.0002, lon=-111.9997),
                    Coordinate(lat=33.00028, lon=-111.9997),
                    Coordinate(lat=33.00028, lon=-111.9998),
                    Coordinate(lat=33.0002, lon=-111.9998),
                ],
                bbox=BoundingBox(
                    min_lat=33.0002,
                    min_lon=-111.9998,
                    max_lat=33.00028,
                    max_lon=-111.9997,
                ),
                area_m2=80.0,
            )
        ]

        candidate = solar_candidate(cell, 8, buildings=buildings, roads=[])

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.metadata["validity_source"], "rooftop_buildings")
        self.assertEqual(
            candidate.metadata["panel_count"],
            len(candidate.metadata["placement_polygons"]),
        )
        self.assertAlmostEqual(
            candidate.metadata["packed_usable_area_m2"],
            candidate.metadata["panel_count"] * 2.0,
            places=2,
        )

    def test_merge_solar_candidates_keeps_rooftop_sites_separate(self) -> None:
        rooftop_polygon_a = [
            Coordinate(lat=33.0001, lon=-112.0000),
            Coordinate(lat=33.0001, lon=-111.9997),
            Coordinate(lat=33.0003, lon=-111.9997),
            Coordinate(lat=33.0003, lon=-112.0000),
        ]
        rooftop_polygon_b = [
            Coordinate(lat=33.0001, lon=-111.9995),
            Coordinate(lat=33.0001, lon=-111.9992),
            Coordinate(lat=33.0003, lon=-111.9992),
            Coordinate(lat=33.0003, lon=-111.9995),
        ]
        candidates = [
            CandidateRegion(
                id="solar-1",
                use_type="solar",
                polygon=rooftop_polygon_a,
                area_m2=75.0,
                feasibility_score=84.0,
                reasoning=["roof", "fit", "packed"],
                estimated_annual_output_kwh=12_000.0,
                estimated_installation_cost_usd=24_000.0,
                metadata={
                    "validity_source": "rooftop_buildings",
                    "panel_count": 18,
                    "installed_capacity_kw": 8.1,
                    "packed_usable_area_m2": 39.24,
                    "valid_region_polygons": [[point.model_dump() for point in rooftop_polygon_a]],
                    "placement_polygons": [[point.model_dump() for point in rooftop_polygon_a]],
                },
            ),
            CandidateRegion(
                id="solar-2",
                use_type="solar",
                polygon=rooftop_polygon_b,
                area_m2=82.0,
                feasibility_score=82.0,
                reasoning=["roof", "fit", "packed"],
                estimated_annual_output_kwh=13_000.0,
                estimated_installation_cost_usd=26_000.0,
                metadata={
                    "validity_source": "rooftop_buildings",
                    "panel_count": 20,
                    "installed_capacity_kw": 9.0,
                    "packed_usable_area_m2": 43.6,
                    "valid_region_polygons": [[point.model_dump() for point in rooftop_polygon_b]],
                    "placement_polygons": [[point.model_dump() for point in rooftop_polygon_b]],
                },
            ),
        ]

        merged = _merge_solar_candidates(candidates, 120.0)

        self.assertEqual(len(merged), 2)
        self.assertEqual([candidate.id for candidate in merged], ["solar-1", "solar-2"])

    def test_wind_candidate_excludes_the_road_corridor_from_display_polygon(self) -> None:
        cell_bbox = BoundingBox(
            min_lat=40.0000,
            min_lon=-86.0000,
            max_lat=40.0050,
            max_lon=-85.9950,
        )
        cell = {
            "id": "cell-wind",
            "center_lat": 40.0025,
            "center_lon": -85.9975,
            "polygon": [
                Coordinate(lat=40.0000, lon=-86.0000),
                Coordinate(lat=40.0000, lon=-85.9950),
                Coordinate(lat=40.0050, lon=-85.9950),
                Coordinate(lat=40.0050, lon=-86.0000),
            ],
            "bbox": cell_bbox,
            "area_m2": 250_000.0,
            "built_ratio": 0.01,
            "vegetation_ratio": 0.08,
            "water_ratio": 0.0,
            "unobstructed_ratio": 0.94,
            "slope_deg": 1.3,
            "road_distance_m": 80.0,
            "water_features": [],
        }
        imagery = ImageryRaster(
            provider="usgs",
            source="test-raster",
            width=24,
            height=24,
            bbox=cell_bbox,
            rows=[[(120, 120, 120, 255) for _ in range(24)] for _ in range(24)],
        )
        road = RoadFeature(
            points=[
                Coordinate(lat=40.0000, lon=-85.9975),
                Coordinate(lat=40.0050, lon=-85.9975),
            ],
            highway_type="primary",
        )

        candidate = wind_candidate(
            cell,
            3,
            imagery=imagery,
            buildings=[],
            roads=[road],
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertNotEqual(candidate.polygon, cell["polygon"])
        self.assertGreater(len(candidate.metadata["valid_region_polygons"]), 0)

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
            water_feature = WaterFeature(
                polygon=[
                    Coordinate(lat=33.0, lon=-112.0),
                    Coordinate(lat=33.0, lon=-111.99),
                    Coordinate(lat=33.01, lon=-111.99),
                    Coordinate(lat=33.01, lon=-112.0),
                ],
                bbox=bbox.__class__(
                    min_lat=33.0,
                    min_lon=-112.0,
                    max_lat=33.01,
                    max_lon=-111.99,
                ),
                area_m2=1000.0,
            )
            return [live_building], [road], [water_feature], "osm-overpass", ["mock vectors"]

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
