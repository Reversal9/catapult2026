from __future__ import annotations

from dataclasses import dataclass

from schemas import BoundingBox, Coordinate


@dataclass(frozen=True)
class ImageryRaster:
    provider: str
    source: str
    width: int
    height: int
    bbox: BoundingBox
    rows: list[list[tuple[int, int, int, int]]]


@dataclass(frozen=True)
class BuildingFootprint:
    polygon: list[Coordinate]
    bbox: BoundingBox
    area_m2: float


@dataclass(frozen=True)
class RoadFeature:
    points: list[Coordinate]
    highway_type: str
