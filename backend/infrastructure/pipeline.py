from __future__ import annotations

import json
import logging
import math

from geometry import normalize_polygon, polygon_area_and_centroid, polygon_self_intersects
from schemas import BoundingBox, CandidateRegion, Coordinate
from schemas import (
    InfrastructureAnalysisRequest,
    InfrastructureAnalysisResponse,
    InfrastructureDataSources,
)

from .common import bbox_for_points
from .grid import build_grid_cells
from .providers.imagery import fetch_imagery_raster
from .providers.terrain import fetch_cell_slopes
from .providers.vector_data import fetch_osm_vectors
from .scoring import (
    data_center_candidate,
    enrich_cells,
    evaluate_solar_candidate,
    wind_candidate,
)
from .segmentation import build_segmentation_features

LOGGER = logging.getLogger("uvicorn.error")


def _polygon_bbox(points: list[Coordinate]) -> BoundingBox:
    return BoundingBox(
        min_lat=min(point.lat for point in points),
        min_lon=min(point.lon for point in points),
        max_lat=max(point.lat for point in points),
        max_lon=max(point.lon for point in points),
    )


def _bbox_gap_m(a: BoundingBox, b: BoundingBox) -> float:
    lat_gap = max(0.0, max(a.min_lat - b.max_lat, b.min_lat - a.max_lat))
    lon_gap = max(0.0, max(a.min_lon - b.max_lon, b.min_lon - a.max_lon))
    reference_lat = math.radians((a.min_lat + a.max_lat + b.min_lat + b.max_lat) / 4.0)
    lat_gap_m = lat_gap * 111_320.0
    lon_gap_m = lon_gap * 111_320.0 * max(0.25, math.cos(reference_lat))
    return math.hypot(lat_gap_m, lon_gap_m)


def _flatten_polygons(candidate: CandidateRegion, key: str) -> list[list[Coordinate]]:
    polygons = candidate.metadata.get(key) or []
    return [
        [Coordinate.model_validate(point) for point in polygon]
        for polygon in polygons
    ]


def _merge_solar_candidates(
    candidates: list[CandidateRegion],
    cell_size_m: float,
) -> list[CandidateRegion]:
    if not candidates:
        return []

    adjacency_gap_m = max(24.0, cell_size_m * 0.18)
    candidate_bboxes = []
    for candidate in candidates:
        valid_polygons = _flatten_polygons(candidate, "valid_region_polygons") or [candidate.polygon]
        bbox = BoundingBox(
            min_lat=min(_polygon_bbox(polygon).min_lat for polygon in valid_polygons),
            min_lon=min(_polygon_bbox(polygon).min_lon for polygon in valid_polygons),
            max_lat=max(_polygon_bbox(polygon).max_lat for polygon in valid_polygons),
            max_lon=max(_polygon_bbox(polygon).max_lon for polygon in valid_polygons),
        )
        candidate_bboxes.append(bbox)

    visited = [False] * len(candidates)
    merged: list[CandidateRegion] = []

    for start_index, candidate in enumerate(candidates):
        if visited[start_index]:
            continue
        stack = [start_index]
        visited[start_index] = True
        cluster_indices: list[int] = []

        while stack:
            current_index = stack.pop()
            cluster_indices.append(current_index)
            current_bbox = candidate_bboxes[current_index]
            current_source = str(
                candidates[current_index].metadata.get("validity_source", "")
            )
            for next_index in range(len(candidates)):
                if visited[next_index]:
                    continue
                next_source = str(candidates[next_index].metadata.get("validity_source", ""))
                if current_source != next_source:
                    continue
                if current_source == "rooftop_buildings":
                    continue
                if _bbox_gap_m(current_bbox, candidate_bboxes[next_index]) > adjacency_gap_m:
                    continue
                visited[next_index] = True
                stack.append(next_index)

        cluster_candidates = [candidates[index] for index in cluster_indices]
        if len(cluster_candidates) == 1:
            merged.append(cluster_candidates[0])
            continue
        valid_region_polygons = [
            polygon
            for cluster_candidate in cluster_candidates
            for polygon in (
                _flatten_polygons(cluster_candidate, "valid_region_polygons")
                or [cluster_candidate.polygon]
            )
        ]
        packing_block_polygons = [
            polygon
            for cluster_candidate in cluster_candidates
            for polygon in _flatten_polygons(cluster_candidate, "packing_block_polygons")
        ]
        placement_polygons = [
            polygon
            for cluster_candidate in cluster_candidates
            for polygon in _flatten_polygons(cluster_candidate, "placement_polygons")
        ]
        cluster_area_m2 = sum(cluster_candidate.area_m2 for cluster_candidate in cluster_candidates)
        weighted_score = (
            sum(cluster_candidate.feasibility_score * cluster_candidate.area_m2 for cluster_candidate in cluster_candidates)
            / max(cluster_area_m2, 1.0)
        )
        annual_output_kwh = sum(
            cluster_candidate.estimated_annual_output_kwh or 0.0
            for cluster_candidate in cluster_candidates
        )
        total_cost_usd = sum(
            cluster_candidate.estimated_installation_cost_usd
            for cluster_candidate in cluster_candidates
        )
        panel_count = sum(
            int(cluster_candidate.metadata.get("panel_count", 0))
            for cluster_candidate in cluster_candidates
        )
        installed_capacity_kw = sum(
            float(cluster_candidate.metadata.get("installed_capacity_kw", 0.0))
            for cluster_candidate in cluster_candidates
        )
        packed_usable_area_m2 = sum(
            float(cluster_candidate.metadata.get("packed_usable_area_m2", 0.0))
            for cluster_candidate in cluster_candidates
        )
        display_panel_count = sum(
            int(cluster_candidate.metadata.get("display_panel_count", 0))
            for cluster_candidate in cluster_candidates
        )
        model_sources = sorted(
            {
                str(cluster_candidate.metadata.get("model_source"))
                for cluster_candidate in cluster_candidates
                if cluster_candidate.metadata.get("model_source")
            }
        )
        weather_sources = sorted(
            {
                str(cluster_candidate.metadata.get("weather_source"))
                for cluster_candidate in cluster_candidates
                if cluster_candidate.metadata.get("weather_source")
            }
        )
        primary_polygon = (
            max(
                valid_region_polygons,
                key=lambda polygon: (
                    (_polygon_bbox(polygon).max_lat - _polygon_bbox(polygon).min_lat)
                    * (_polygon_bbox(polygon).max_lon - _polygon_bbox(polygon).min_lon)
                ),
            )
            if valid_region_polygons
            else candidate.polygon
        )
        merged.append(
            CandidateRegion(
                id=f"solar-cluster-{len(merged) + 1}",
                use_type="solar",
                polygon=primary_polygon,
                area_m2=round(cluster_area_m2, 2),
                feasibility_score=round(weighted_score, 1),
                reasoning=[
                    "Adjacent solar-valid cells were merged into a contiguous siting region for display and summary metrics.",
                    cluster_candidates[0].reasoning[1],
                    "Packed solar blocks are drawn only inside the screened valid footprints for the merged region.",
                ],
                estimated_annual_output_kwh=round(annual_output_kwh, 2),
                estimated_installation_cost_usd=round(total_cost_usd, 2),
                metadata={
                    "model_source": ",".join(model_sources) if model_sources else "infrastructure-heuristic",
                    "weather_source": ",".join(weather_sources) if weather_sources else "not-applicable",
                    "panel_count": panel_count,
                    "installed_capacity_kw": round(installed_capacity_kw, 2),
                    "usable_solar_area_m2": round(cluster_area_m2, 2),
                    "packed_usable_area_m2": round(packed_usable_area_m2, 2),
                    "display_panel_count": display_panel_count,
                    "valid_region_polygons": [
                        [point.model_dump() for point in polygon]
                        for polygon in valid_region_polygons
                    ],
                    "packing_block_polygons": [
                        [point.model_dump() for point in polygon]
                        for polygon in packing_block_polygons
                    ],
                    "placement_polygons": [
                        [point.model_dump() for point in polygon]
                        for polygon in placement_polygons
                    ],
                    "validity_source": str(candidate.metadata.get("validity_source", "merged_open_land")),
                },
            )
        )

    return merged


def analyze_infrastructure_polygon(
    request: InfrastructureAnalysisRequest,
) -> InfrastructureAnalysisResponse:
    polygon = normalize_polygon(request.points)
    if polygon_self_intersects(polygon):
        raise ValueError("Polygon is self-intersecting. Provide a simple non-intersecting polygon.")

    area_m2, centroid = polygon_area_and_centroid(polygon)
    bbox = bbox_for_points(polygon)
    allowed_use_types = set(request.allowed_use_types)
    effective_cell_size_m = request.cell_size_m
    cells = build_grid_cells(polygon, bbox, effective_cell_size_m)
    if allowed_use_types == {"solar"}:
        while len(cells) < 4 and effective_cell_size_m > 100.0:
            next_cell_size_m = max(100.0, effective_cell_size_m / 2.0)
            if next_cell_size_m == effective_cell_size_m:
                break
            effective_cell_size_m = next_cell_size_m
            cells = build_grid_cells(polygon, bbox, effective_cell_size_m)

    imagery_raster, imagery_source, imagery_notes = fetch_imagery_raster(
        request.imagery_provider,
        bbox,
    )
    buildings, roads, water_features, vector_source, vector_notes = fetch_osm_vectors(bbox)
    slopes_by_cell, terrain_source, terrain_notes = fetch_cell_slopes(
        cells,
        provider=request.terrain_provider,
    )
    segmentation_features, segmentation_source, segmentation_notes = build_segmentation_features(
        cells,
        imagery_raster,
        request.segmentation_backend,
    )

    enrich_cells(
        cells,
        segmentation_features=segmentation_features,
        segmentation_source=segmentation_source,
        imagery_source=imagery_source,
        buildings=buildings,
        roads=roads,
        waters=water_features,
        vector_source=vector_source,
        slopes_by_cell=slopes_by_cell,
        terrain_source=terrain_source,
    )

    candidates = []
    pretrim_candidate_counts = {"solar": 0, "wind": 0, "data_center": 0}
    solar_rejections = {
        "low_usable_area": 0,
        "low_panel_count": 0,
        "low_score": 0,
    }
    for index, cell in enumerate(cells, start=1):
        if "solar" in allowed_use_types:
            solar, solar_rejection_reason = evaluate_solar_candidate(
                cell,
                index,
                request.solar_spec,
                imagery_raster,
                buildings,
                roads,
            )
            if solar is not None:
                candidates.append(solar)
                pretrim_candidate_counts["solar"] += 1
            elif solar_rejection_reason in solar_rejections:
                solar_rejections[solar_rejection_reason] += 1
        if "wind" in allowed_use_types:
            candidate = wind_candidate(
                cell,
                index,
                request.wind_spec,
                imagery_raster,
                buildings,
                roads,
            )
            if candidate is not None:
                candidates.append(candidate)
                pretrim_candidate_counts["wind"] += 1
        if "data_center" in allowed_use_types:
            candidate = data_center_candidate(
                cell,
                index,
                request.data_center_spec,
                imagery_raster,
                buildings,
                roads,
            )
            if candidate is not None:
                candidates.append(candidate)
                pretrim_candidate_counts["data_center"] += 1

    if allowed_use_types == {"solar"}:
        candidates = _merge_solar_candidates(
            [candidate for candidate in candidates if candidate.use_type == "solar"],
            request.cell_size_m,
        )

    candidates.sort(key=lambda candidate: candidate.feasibility_score, reverse=True)
    candidates = candidates[:80]

    notes = [
        *imagery_notes,
        *vector_notes,
        *terrain_notes,
        *segmentation_notes,
        "Candidate subregions are grid-derived cells clipped to the polygon interior for stable scoring.",
    ]
    if effective_cell_size_m != request.cell_size_m:
        notes.append(
            f"Solar-only siting refined the grid from {request.cell_size_m:.0f} m to {effective_cell_size_m:.0f} m cells for a smaller site footprint."
        )
    if allowed_use_types == {"solar"}:
        notes.append("Adjacent solar-valid cells were merged into larger siting regions before visualization.")
    if not candidates:
        notes.append("No subregions exceeded feasibility thresholds for the configured cell size.")

    candidate_model_sources = sorted(
        {
            str(candidate.metadata.get("model_source"))
            for candidate in candidates
            if candidate.metadata.get("model_source")
        }
    )
    model_source = (
        ",".join(candidate_model_sources)
        if candidate_model_sources
        else "infrastructure-heuristic"
    )

    candidate_counts = {"solar": 0, "wind": 0, "data_center": 0}
    for candidate in candidates:
        candidate_counts[candidate.use_type] += 1

    debug_payload = {
        "request": {
            "cell_size_m": request.cell_size_m,
            "effective_cell_size_m": effective_cell_size_m,
            "imagery_provider": request.imagery_provider,
            "segmentation_backend": request.segmentation_backend,
            "terrain_provider": request.terrain_provider,
            "include_debug_layers": request.include_debug_layers,
            "point_count": len(request.points),
            "allowed_use_types": request.allowed_use_types,
            "solar_spec": {
                "panel_area_m2": request.solar_spec.panel_area_m2,
                "panel_rating_w": request.solar_spec.panel_rating_w,
                "panel_cost_usd": request.solar_spec.panel_cost_usd,
                "construction_cost_per_m2_usd": request.solar_spec.construction_cost_per_m2_usd,
                "packing_efficiency": request.solar_spec.packing_efficiency,
                "performance_ratio": request.solar_spec.performance_ratio,
                "sunlight_threshold_kwh_m2_yr": request.solar_spec.sunlight_threshold_kwh_m2_yr,
            },
            "wind_spec": {
                "turbine_rating_kw": request.wind_spec.turbine_rating_kw,
                "turbine_cost_usd": request.wind_spec.turbine_cost_usd,
                "spacing_area_m2": request.wind_spec.spacing_area_m2,
                "minimum_viable_wind_speed_mps": request.wind_spec.minimum_viable_wind_speed_mps,
            },
            "data_center_spec": {
                "power_density_kw_per_m2": request.data_center_spec.power_density_kw_per_m2,
                "construction_cost_per_m2_usd": request.data_center_spec.construction_cost_per_m2_usd,
                "fit_out_cost_per_kw_usd": request.data_center_spec.fit_out_cost_per_kw_usd,
            },
        },
        "bbox": {
            "min_lat": round(bbox.min_lat, 6),
            "min_lon": round(bbox.min_lon, 6),
            "max_lat": round(bbox.max_lat, 6),
            "max_lon": round(bbox.max_lon, 6),
        },
        "centroid": {
            "lat": round(centroid.lat, 6),
            "lon": round(centroid.lon, 6),
        },
        "area_m2": round(area_m2, 2),
        "subdivisions_evaluated": len(cells),
        "data_sources": {
            "imagery": imagery_source,
            "vector_data": vector_source,
            "segmentation": segmentation_source,
            "terrain": terrain_source,
        },
        "pretrim_candidate_counts": pretrim_candidate_counts,
        "candidate_counts": candidate_counts,
        "solar_rejections": solar_rejections,
        "model_source": model_source,
        "top_candidate_ids": [candidate.id for candidate in candidates[:5]],
        "pipeline_notes": notes,
    }
    LOGGER.info("[infrastructure-analysis] %s", json.dumps(debug_payload, sort_keys=True))

    return InfrastructureAnalysisResponse(
        area_m2=round(area_m2, 2),
        bbox=bbox,
        centroid=centroid,
        subdivisions_evaluated=len(cells),
        candidates=candidates,
        data_sources=InfrastructureDataSources(
            imagery=imagery_source,
            vector_data=vector_source,
            segmentation=segmentation_source,
            terrain=terrain_source,
        ),
        pipeline_notes=notes,
        model_source=model_source,
    )
