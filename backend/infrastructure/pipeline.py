from __future__ import annotations

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
    solar_candidate,
    wind_candidate,
)
from .segmentation import build_segmentation_features


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
    for index, cell in enumerate(cells, start=1):
        for builder in (solar_candidate, wind_candidate, data_center_candidate):
            candidate = builder(cell, index)
            if candidate is not None:
                candidates.append(candidate)

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
    )
