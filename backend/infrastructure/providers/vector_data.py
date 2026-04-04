from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError

from geometry import polygon_area_and_centroid
from schemas import BoundingBox, Coordinate

from ..common import EXCLUDED_HIGHWAY_TYPES, bbox_for_points
from ..http import http_post_form
from ..models import BuildingFootprint, RoadFeature


OVERPASS_INTERPRETER_URL = os.getenv(
    "OSM_OVERPASS_URL",
    "https://overpass-api.de/api/interpreter",
)


def fetch_osm_vectors(
    bbox: BoundingBox,
) -> tuple[list[BuildingFootprint], list[RoadFeature], str, list[str]]:
    query = f"""
[out:json][timeout:25];
(
  way["building"]({bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon});
  way["highway"]({bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon});
);
out geom;
""".strip()

    try:
        payload = json.loads(
            http_post_form(
                OVERPASS_INTERPRETER_URL,
                {"data": query},
                headers={"Accept": "application/json"},
            ).decode("utf-8")
        )
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        return [], [], "osm-overpass-fallback", [
            f"OpenStreetMap vectors could not be retrieved ({error.__class__.__name__}); built/access features used deterministic fallbacks.",
        ]

    buildings: list[BuildingFootprint] = []
    roads: list[RoadFeature] = []

    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue

        tags = element.get("tags", {})
        coordinates = [
            Coordinate(lat=vertex["lat"], lon=vertex["lon"])
            for vertex in element.get("geometry", [])
            if "lat" in vertex and "lon" in vertex
        ]

        if "building" in tags:
            if len(coordinates) < 3:
                continue
            if coordinates[0] != coordinates[-1]:
                coordinates = [*coordinates, coordinates[0]]
            try:
                area_m2, _ = polygon_area_and_centroid(coordinates)
            except ValueError:
                continue
            buildings.append(
                BuildingFootprint(
                    polygon=coordinates,
                    bbox=bbox_for_points(coordinates),
                    area_m2=area_m2,
                )
            )
            continue

        highway_type = tags.get("highway", "")
        if highway_type in EXCLUDED_HIGHWAY_TYPES or len(coordinates) < 2:
            continue
        roads.append(RoadFeature(points=coordinates, highway_type=highway_type))

    return (
        buildings,
        roads,
        "osm-overpass",
        [
            f"OpenStreetMap returned {len(buildings)} building footprints and {len(roads)} road polylines for live feature extraction.",
        ],
    )
