from __future__ import annotations

import json
import logging

from geometry import normalize_polygon, polygon_area_and_centroid, polygon_self_intersects
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
    solar_candidate,
    wind_candidate,
)
from .segmentation import build_segmentation_features

LOGGER = logging.getLogger("uvicorn.error")


def analyze_infrastructure_polygon(
    request: InfrastructureAnalysisRequest,
) -> InfrastructureAnalysisResponse:
    polygon = normalize_polygon(request.points)
    if polygon_self_intersects(polygon):
        raise ValueError("Polygon is self-intersecting. Provide a simple non-intersecting polygon.")

    area_m2, centroid = polygon_area_and_centroid(polygon)
    bbox = bbox_for_points(polygon)
    cells = build_grid_cells(polygon, bbox, request.cell_size_m)

    imagery_raster, imagery_source, imagery_notes = fetch_imagery_raster(
        request.imagery_provider,
        bbox,
    )
    buildings, roads, vector_source, vector_notes = fetch_osm_vectors(bbox)
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
    allowed_use_types = set(request.allowed_use_types)
    for index, cell in enumerate(cells, start=1):
        if "solar" in allowed_use_types:
            solar, solar_rejection_reason = evaluate_solar_candidate(
                cell,
                index,
                request.solar_spec,
            )
            if solar is not None:
                candidates.append(solar)
                pretrim_candidate_counts["solar"] += 1
            elif solar_rejection_reason in solar_rejections:
                solar_rejections[solar_rejection_reason] += 1
        if "wind" in allowed_use_types:
            candidate = wind_candidate(cell, index)
            if candidate is not None:
                candidates.append(candidate)
                pretrim_candidate_counts["wind"] += 1
        if "data_center" in allowed_use_types:
            candidate = data_center_candidate(cell, index)
            if candidate is not None:
                candidates.append(candidate)
                pretrim_candidate_counts["data_center"] += 1

    candidates.sort(key=lambda candidate: candidate.feasibility_score, reverse=True)
    candidates = candidates[:80]

    notes = [
        *imagery_notes,
        *vector_notes,
        *terrain_notes,
        *segmentation_notes,
        "Candidate subregions are grid-derived cells clipped to the polygon interior for stable scoring.",
    ]
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
