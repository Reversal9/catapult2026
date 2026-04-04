from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from schemas import Coordinate


EARTH_RADIUS_M = 6_371_000.0
EPSILON = 1e-12


@dataclass(frozen=True)
class ProjectedPoint:
    x: float
    y: float


def normalize_polygon(points: Iterable[Coordinate]) -> list[Coordinate]:
    polygon = list(points)
    if len(polygon) < 3:
        raise ValueError("Polygon needs at least three points.")
    if polygon[0].lat == polygon[-1].lat and polygon[0].lon == polygon[-1].lon:
        polygon = polygon[:-1]
    if len(polygon) < 3:
        raise ValueError("Polygon needs at least three points.")
    unique_points = {
        (round(point.lat, 7), round(point.lon, 7)) for point in polygon
    }
    if len(unique_points) < 3:
        raise ValueError("Polygon needs at least three distinct points.")
    return polygon


def unwrap_longitudes(points: list[Coordinate]) -> list[Coordinate]:
    if not points:
        return []

    unwrapped = [Coordinate(lat=points[0].lat, lon=points[0].lon)]
    previous_lon = points[0].lon

    for point in points[1:]:
        lon = point.lon
        while lon - previous_lon > 180:
            lon -= 360
        while lon - previous_lon < -180:
            lon += 360
        unwrapped.append(Coordinate(lat=point.lat, lon=lon))
        previous_lon = lon

    return unwrapped


def project_polygon(points: list[Coordinate]) -> list[ProjectedPoint]:
    points = unwrap_longitudes(points)
    lat0 = sum(point.lat for point in points) / len(points)
    lon0 = sum(point.lon for point in points) / len(points)
    cos_lat0 = math.cos(math.radians(lat0)) or 1.0

    projected = []
    for point in points:
        x = math.radians(point.lon - lon0) * EARTH_RADIUS_M * cos_lat0
        y = math.radians(point.lat - lat0) * EARTH_RADIUS_M
        projected.append(ProjectedPoint(x=x, y=y))
    return projected


def polygon_area_and_centroid(points: list[Coordinate]) -> tuple[float, Coordinate]:
    polygon = normalize_polygon(points)
    projected = project_polygon(polygon)
    area_twice = 0.0
    centroid_x = 0.0
    centroid_y = 0.0

    for index in range(len(projected)):
        next_index = (index + 1) % len(projected)
        p1 = projected[index]
        p2 = projected[next_index]
        cross = p1.x * p2.y - p2.x * p1.y
        area_twice += cross
        centroid_x += (p1.x + p2.x) * cross
        centroid_y += (p1.y + p2.y) * cross

    area_m2 = abs(area_twice) / 2.0
    if area_m2 == 0:
        raise ValueError("Polygon area is zero.")

    centroid_x /= 3.0 * area_twice
    centroid_y /= 3.0 * area_twice

    lat0 = sum(point.lat for point in polygon) / len(polygon)
    lon0 = sum(point.lon for point in polygon) / len(polygon)
    cos_lat0 = math.cos(math.radians(lat0)) or 1.0
    centroid = Coordinate(
        lat=lat0 + math.degrees(centroid_y / EARTH_RADIUS_M),
        lon=lon0 + math.degrees(centroid_x / (EARTH_RADIUS_M * cos_lat0)),
    )
    return area_m2, centroid


def _orientation(a: Coordinate, b: Coordinate, c: Coordinate) -> float:
    return (b.lon - a.lon) * (c.lat - a.lat) - (b.lat - a.lat) * (c.lon - a.lon)


def _on_segment(a: Coordinate, b: Coordinate, c: Coordinate) -> bool:
    return (
        min(a.lon, b.lon) <= c.lon <= max(a.lon, b.lon)
        and min(a.lat, b.lat) <= c.lat <= max(a.lat, b.lat)
    )


def _segments_intersect(
    a1: Coordinate,
    a2: Coordinate,
    b1: Coordinate,
    b2: Coordinate,
) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if abs(o1) < EPSILON and _on_segment(a1, a2, b1):
        return True
    if abs(o2) < EPSILON and _on_segment(a1, a2, b2):
        return True
    if abs(o3) < EPSILON and _on_segment(b1, b2, a1):
        return True
    if abs(o4) < EPSILON and _on_segment(b1, b2, a2):
        return True

    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def polygon_self_intersects(points: list[Coordinate]) -> bool:
    polygon = normalize_polygon(points)
    n = len(polygon)
    for i in range(n):
        a1 = polygon[i]
        a2 = polygon[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1:
                continue
            if i == 0 and j == n - 1:
                continue

            b1 = polygon[j]
            b2 = polygon[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False