from __future__ import annotations

import hashlib
import math
import os

from schemas import BoundingBox, Coordinate


EXCLUDED_HIGHWAY_TYPES = {
    "bridleway",
    "construction",
    "corridor",
    "cycleway",
    "footway",
    "path",
    "pedestrian",
    "proposed",
    "steps",
}


def bbox_for_points(points: list[Coordinate]) -> BoundingBox:
    return BoundingBox(
        min_lat=min(point.lat for point in points),
        min_lon=min(point.lon for point in points),
        max_lat=max(point.lat for point in points),
        max_lon=max(point.lon for point in points),
    )


def point_in_polygon(lat: float, lon: float, polygon: list[Coordinate]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        yi = polygon[i].lat
        xi = polygon[i].lon
        yj = polygon[j].lat
        xj = polygon[j].lon

        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def pseudo(lat: float, lon: float, salt: str) -> float:
    digest = hashlib.sha256(f"{lat:.6f}:{lon:.6f}:{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def solar_irradiance_proxy(lat: float) -> float:
    # Conservative continental-scale proxy for infrastructure screening only.
    # Keep the floor high enough that mid-latitude regions can still surface
    # buildable candidates before the shared solar model refines output.
    return max(1250.0, 2450.0 - 18.0 * abs(lat))


def wind_speed_proxy(lat: float, lon: float) -> float:
    speed = 5.6
    if 35 < lat < 50 and -105 < lon < -85:
        speed += 2.0
    if lat > 45:
        speed += 0.8
    if lon < -115 or lon > -75:
        speed += 0.5
    return speed


def imagery_size(default: int = 256) -> int:
    return safe_env_int("INFRASTRUCTURE_IMAGERY_SIZE", default, 96, 512)


def safe_env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(high, value))


def bbox_within_conus(bounds: BoundingBox) -> bool:
    return (
        24.0 <= bounds.min_lat <= 50.0
        and 24.0 <= bounds.max_lat <= 50.0
        and -125.5 <= bounds.min_lon <= -66.0
        and -125.5 <= bounds.max_lon <= -66.0
    )
