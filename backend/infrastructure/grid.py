from __future__ import annotations

import math

from geometry import polygon_area_and_centroid
from schemas import BoundingBox, Coordinate

from .common import bbox_for_points, clamp, point_in_polygon
from .models import BuildingFootprint, RoadFeature


def build_grid_cells(
    polygon: list[Coordinate],
    bbox: BoundingBox,
    cell_size_m: float,
) -> list[dict]:
    lat_step = cell_size_m / 111_320.0
    center_lat = (bbox.min_lat + bbox.max_lat) / 2.0
    lon_step = cell_size_m / (111_320.0 * max(0.25, math.cos(math.radians(center_lat))))
    cell_area_m2 = cell_size_m * cell_size_m

    cells: list[dict] = []
    lat = bbox.min_lat + lat_step / 2.0
    index = 1
    while lat < bbox.max_lat:
        lon = bbox.min_lon + lon_step / 2.0
        while lon < bbox.max_lon:
            if point_in_polygon(lat, lon, polygon):
                half_lat = lat_step / 2.0
                half_lon = lon_step / 2.0
                cell_polygon = [
                    Coordinate(lat=lat - half_lat, lon=lon - half_lon),
                    Coordinate(lat=lat - half_lat, lon=lon + half_lon),
                    Coordinate(lat=lat + half_lat, lon=lon + half_lon),
                    Coordinate(lat=lat + half_lat, lon=lon - half_lon),
                ]
                cells.append(
                    {
                        "id": f"cell-{index}",
                        "center_lat": lat,
                        "center_lon": lon,
                        "polygon": cell_polygon,
                        "bbox": bbox_for_points(cell_polygon),
                        "area_m2": cell_area_m2,
                        "cell_size_m": cell_size_m,
                    }
                )
                index += 1
            lon += lon_step
        lat += lat_step

    return cells


def line_intersection_at_lat(a: Coordinate, b: Coordinate, latitude: float) -> Coordinate:
    if abs(b.lat - a.lat) < 1e-12:
        return Coordinate(lat=latitude, lon=a.lon)
    ratio = (latitude - a.lat) / (b.lat - a.lat)
    return Coordinate(lat=latitude, lon=a.lon + ratio * (b.lon - a.lon))


def line_intersection_at_lon(a: Coordinate, b: Coordinate, longitude: float) -> Coordinate:
    if abs(b.lon - a.lon) < 1e-12:
        return Coordinate(lat=a.lat, lon=longitude)
    ratio = (longitude - a.lon) / (b.lon - a.lon)
    return Coordinate(lat=a.lat + ratio * (b.lat - a.lat), lon=longitude)


def clip_polygon_to_bbox(points: list[Coordinate], bbox: BoundingBox) -> list[Coordinate]:
    clipped = points[:]

    def clip_with_boundary(current: list[Coordinate], inside, intersect) -> list[Coordinate]:
        if not current:
            return []
        result: list[Coordinate] = []
        previous = current[-1]
        previous_inside = inside(previous)

        for point in current:
            point_inside = inside(point)
            if point_inside:
                if not previous_inside:
                    result.append(intersect(previous, point))
                result.append(point)
            elif previous_inside:
                result.append(intersect(previous, point))
            previous = point
            previous_inside = point_inside
        return result

    clipped = clip_with_boundary(
        clipped,
        lambda point: point.lon >= bbox.min_lon,
        lambda start, end: line_intersection_at_lon(start, end, bbox.min_lon),
    )
    clipped = clip_with_boundary(
        clipped,
        lambda point: point.lon <= bbox.max_lon,
        lambda start, end: line_intersection_at_lon(start, end, bbox.max_lon),
    )
    clipped = clip_with_boundary(
        clipped,
        lambda point: point.lat >= bbox.min_lat,
        lambda start, end: line_intersection_at_lat(start, end, bbox.min_lat),
    )
    clipped = clip_with_boundary(
        clipped,
        lambda point: point.lat <= bbox.max_lat,
        lambda start, end: line_intersection_at_lat(start, end, bbox.max_lat),
    )

    if clipped and clipped[0] != clipped[-1]:
        clipped.append(clipped[0])
    return clipped


def bbox_overlaps(a: BoundingBox, b: BoundingBox) -> bool:
    return not (
        a.max_lat <= b.min_lat
        or a.min_lat >= b.max_lat
        or a.max_lon <= b.min_lon
        or a.min_lon >= b.max_lon
    )


def overlap_building_area_m2(cell_bbox: BoundingBox, building: BuildingFootprint) -> float:
    if not bbox_overlaps(cell_bbox, building.bbox):
        return 0.0
    if (
        building.bbox.min_lat >= cell_bbox.min_lat
        and building.bbox.max_lat <= cell_bbox.max_lat
        and building.bbox.min_lon >= cell_bbox.min_lon
        and building.bbox.max_lon <= cell_bbox.max_lon
    ):
        return building.area_m2

    clipped = clip_polygon_to_bbox(building.polygon, cell_bbox)
    if len(clipped) < 4:
        return 0.0
    try:
        area_m2, _ = polygon_area_and_centroid(clipped)
    except ValueError:
        return 0.0
    return area_m2


def distance_point_to_segment_m(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    reference_lat = math.radians(point.lat)
    lon_scale = 111_320.0 * max(0.25, math.cos(reference_lat))
    lat_scale = 111_320.0

    ax = (start.lon - point.lon) * lon_scale
    ay = (start.lat - point.lat) * lat_scale
    bx = (end.lon - point.lon) * lon_scale
    by = (end.lat - point.lat) * lat_scale

    dx = bx - ax
    dy = by - ay
    segment_length_sq = dx * dx + dy * dy
    if segment_length_sq <= 1e-9:
        return math.hypot(ax, ay)

    projection = -((ax * dx) + (ay * dy)) / segment_length_sq
    projection = clamp(projection, 0.0, 1.0)
    closest_x = ax + projection * dx
    closest_y = ay + projection * dy
    return math.hypot(closest_x, closest_y)


def nearest_road_distance_m(point: Coordinate, roads: list[RoadFeature]) -> float:
    best = float("inf")
    for road in roads:
        for index in range(len(road.points) - 1):
            distance = distance_point_to_segment_m(point, road.points[index], road.points[index + 1])
            if distance < best:
                best = distance
    return best if math.isfinite(best) else 4_000.0
