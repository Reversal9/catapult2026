"""Compatibility wrapper for the modular infrastructure pipeline package."""

from infrastructure import (
    BuildingFootprint,
    ImageryRaster,
    RoadFeature,
    analyze_infrastructure_polygon,
)

__all__ = [
    "BuildingFootprint",
    "ImageryRaster",
    "RoadFeature",
    "analyze_infrastructure_polygon",
]
