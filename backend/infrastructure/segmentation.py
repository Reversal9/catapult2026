from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError

from schemas import BoundingBox

from .common import clamp, pseudo
from .http import http_post_json
from .models import ImageryRaster


REMOTE_BACKENDS = {
    "unet": "INFRA_UNET_ENDPOINT",
    "mask_rcnn": "INFRA_MASK_RCNN_ENDPOINT",
}


def resolve_segmentation_backend(requested: str) -> str:
    if requested == "auto":
        for backend, env_name in REMOTE_BACKENDS.items():
            if os.getenv(env_name):
                return backend
        return "hybrid"
    return requested


def build_segmentation_features(
    cells: list[dict],
    imagery: ImageryRaster | None,
    requested_backend: str,
) -> tuple[dict[str, dict[str, float]], str, list[str]]:
    features: dict[str, dict[str, float]] = {}
    for cell in cells:
        features[cell["id"]] = (
            sample_imagery_features(imagery, cell["bbox"]) if imagery else None
        ) or proxy_landcover(cell)

    backend = resolve_segmentation_backend(requested_backend)
    if backend == "rule_based":
        source = "rgb-landcover-heuristics" if imagery else "rule-based-heuristics"
        notes = [
            "Rule-based segmentation classified imagery into vegetation, water, shadow, and impervious signals.",
        ]
        if not imagery:
            notes.append("No live imagery was available, so segmentation used deterministic spatial fallbacks.")
        return features, source, notes

    remote_features, remote_source, remote_notes = run_remote_segmentation(
        cells,
        imagery,
        backend,
    )
    if backend in {"unet", "mask_rcnn"} and remote_features is None:
        return build_segmentation_features(cells, imagery, "rule_based")

    if remote_features is not None:
        for cell_id, cell_features in remote_features.items():
            features[cell_id].update(cell_features)

    if backend == "hybrid":
        source = remote_source or (
            "hybrid-segmentation" if imagery else "rule-based-heuristics"
        )
        notes = [
            "Hybrid segmentation merges rule-based raster cues with any configured ML cell outputs.",
            *remote_notes,
        ]
        return features, source, notes

    return (
        features,
        remote_source or f"{backend}-fallback-heuristics",
        remote_notes or ["Requested ML segmentation backend was unavailable, so heuristics were used."],
    )


def run_remote_segmentation(
    cells: list[dict],
    imagery: ImageryRaster | None,
    backend: str,
) -> tuple[dict[str, dict[str, float]] | None, str | None, list[str]]:
    if not imagery:
        return None, None, [
            f"{backend} segmentation was requested but no imagery raster was available for inference.",
        ]

    env_name = REMOTE_BACKENDS.get(backend)
    if backend == "hybrid":
        for candidate_backend, candidate_env in REMOTE_BACKENDS.items():
            if os.getenv(candidate_env):
                return run_remote_segmentation(cells, imagery, candidate_backend)
        return None, None, [
            "No remote segmentation endpoint was configured, so hybrid mode used rule-based segmentation only.",
        ]
    if not env_name or not os.getenv(env_name):
        return None, None, [
            f"{backend} segmentation was requested but {env_name or 'the endpoint env var'} was not set.",
        ]

    payload = {
        "bbox": imagery.bbox.model_dump(),
        "width": imagery.width,
        "height": imagery.height,
        "pixels": imagery.rows,
        "cells": [
            {
                "id": cell["id"],
                "bbox": cell["bbox"].model_dump(),
            }
            for cell in cells
        ],
    }

    try:
        response = json.loads(
            http_post_json(os.getenv(env_name), payload).decode("utf-8")
        )
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        return None, None, [
            f"{backend} segmentation endpoint failed ({error.__class__.__name__}); heuristics were used instead.",
        ]

    remote_features: dict[str, dict[str, float]] = {}
    for item in response.get("cells", []):
        cell_id = item.get("id")
        if not cell_id:
            continue
        remote_features[cell_id] = {
            key: clamp(float(value), 0.0, 1.0)
            for key, value in item.items()
            if key
            in {
                "vegetation_ratio",
                "water_ratio",
                "impervious_ratio",
                "shadow_ratio",
                "building_ratio",
            }
            and value is not None
        }

    return (
        remote_features,
        response.get("source") or backend,
        [f"Remote {backend} segmentation results were merged into cell-level features."],
    )


def sample_imagery_features(
    raster: ImageryRaster | None,
    cell_bbox: BoundingBox,
) -> dict[str, float] | None:
    if raster is None:
        return None

    lat_span = raster.bbox.max_lat - raster.bbox.min_lat
    lon_span = raster.bbox.max_lon - raster.bbox.min_lon
    if lat_span <= 1e-12 or lon_span <= 1e-12:
        return None

    min_x = int((cell_bbox.min_lon - raster.bbox.min_lon) / lon_span * raster.width)
    max_x = int((cell_bbox.max_lon - raster.bbox.min_lon) / lon_span * raster.width + 0.9999)
    min_y = int((raster.bbox.max_lat - cell_bbox.max_lat) / lat_span * raster.height)
    max_y = int((raster.bbox.max_lat - cell_bbox.min_lat) / lat_span * raster.height + 0.9999)

    min_x = max(0, min(raster.width - 1, min_x))
    max_x = max(min_x + 1, min(raster.width, max_x))
    min_y = max(0, min(raster.height - 1, min_y))
    max_y = max(min_y + 1, min(raster.height, max_y))

    vegetation = 0
    water = 0
    bright_impervious = 0
    dark_pixels = 0
    usable = 0

    for y in range(min_y, max_y):
        row = raster.rows[y]
        for x in range(min_x, max_x):
            red, green, blue, alpha = row[x]
            if alpha == 0:
                continue
            usable += 1
            brightness = (red + green + blue) / 3.0
            saturation = max(red, green, blue) - min(red, green, blue)

            if green > red * 1.08 and green > blue * 1.04 and brightness > 40:
                vegetation += 1
            if blue > red * 1.12 and blue > green * 1.03 and brightness > 35:
                water += 1
            if brightness > 140 and saturation < 55:
                bright_impervious += 1
            if brightness < 60:
                dark_pixels += 1

    if usable == 0:
        return None

    return {
        "vegetation_ratio": vegetation / usable,
        "water_ratio": water / usable,
        "impervious_ratio": bright_impervious / usable,
        "shadow_ratio": dark_pixels / usable,
    }


def proxy_landcover(cell: dict) -> dict[str, float]:
    return {
        "vegetation_ratio": 0.15 + 0.5 * pseudo(cell["center_lat"], cell["center_lon"], "veg"),
        "water_ratio": 0.03 * pseudo(cell["center_lat"], cell["center_lon"], "water"),
        "impervious_ratio": 0.1 + 0.45 * pseudo(cell["center_lat"], cell["center_lon"], "built"),
        "shadow_ratio": 0.15 + 0.45 * pseudo(cell["center_lat"], cell["center_lon"], "shade"),
    }
