from __future__ import annotations

import math
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from schemas import Coordinate

from ..common import clamp, pseudo
from ..http import http_get_json


DEFAULT_DATASET = "mapzen"
OPEN_TOPO_DATA_URL = "https://api.opentopodata.org/v1"


def fetch_cell_slopes(
    cells: list[dict],
    provider: str = "opentopodata",
) -> tuple[dict[str, float], str, list[str]]:
    if provider != "opentopodata":
        return proxy_cell_slopes(cells), "proxy-slope", [
            "Terrain provider was not configured for live retrieval; slope features used deterministic fallbacks.",
        ]

    dataset = DEFAULT_DATASET
    sample_points: list[tuple[str, Coordinate]] = []
    for cell in cells:
        lat = cell["center_lat"]
        lon = cell["center_lon"]
        half_step = cell["cell_size_m"] / 2.0
        lat_offset = half_step / 111_320.0
        lon_offset = half_step / (
            111_320.0 * max(0.25, math.cos(math.radians(lat)))
        )

        sample_points.extend(
            [
                (f"{cell['id']}:north", Coordinate(lat=lat + lat_offset, lon=lon)),
                (f"{cell['id']}:south", Coordinate(lat=lat - lat_offset, lon=lon)),
                (f"{cell['id']}:east", Coordinate(lat=lat, lon=lon + lon_offset)),
                (f"{cell['id']}:west", Coordinate(lat=lat, lon=lon - lon_offset)),
            ]
        )

    try:
        elevations = fetch_elevations(dataset, sample_points)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        return proxy_cell_slopes(cells), "proxy-slope", [
            f"OpenTopoData elevation retrieval failed ({error.__class__.__name__}); slope features used deterministic fallbacks.",
        ]

    slopes: dict[str, float] = {}
    for cell in cells:
        north = elevations.get(f"{cell['id']}:north")
        south = elevations.get(f"{cell['id']}:south")
        east = elevations.get(f"{cell['id']}:east")
        west = elevations.get(f"{cell['id']}:west")
        if None in {north, south, east, west}:
            slopes[cell["id"]] = proxy_slope(cell)
            continue

        rise_run_ns = abs(float(north) - float(south)) / max(cell["cell_size_m"], 1.0)
        rise_run_ew = abs(float(east) - float(west)) / max(cell["cell_size_m"], 1.0)
        slope_rad = math.atan(max(rise_run_ns, rise_run_ew))
        slopes[cell["id"]] = clamp(math.degrees(slope_rad), 0.1, 35.0)

    return slopes, f"opentopodata:{dataset}", [
        "OpenTopoData elevation samples were used to estimate cell-level slope.",
    ]


def fetch_elevations(
    dataset: str,
    sample_points: list[tuple[str, Coordinate]],
) -> dict[str, float | None]:
    elevations: dict[str, float | None] = {}
    chunk_size = 80
    for start in range(0, len(sample_points), chunk_size):
        chunk = sample_points[start : start + chunk_size]
        locations = "|".join(
            f"{point.lat:.6f},{point.lon:.6f}" for _, point in chunk
        )
        url = f"{OPEN_TOPO_DATA_URL}/{dataset}?locations={quote(locations, safe='|,')}"
        payload = http_get_json(url)
        results = payload.get("results", [])
        if len(results) != len(chunk):
            raise ValueError("Elevation API returned an unexpected number of samples.")
        for (sample_id, _point), item in zip(chunk, results, strict=True):
            elevations[sample_id] = item.get("elevation")
    return elevations


def proxy_cell_slopes(cells: list[dict]) -> dict[str, float]:
    return {cell["id"]: proxy_slope(cell) for cell in cells}


def proxy_slope(cell: dict) -> float:
    return 0.2 + 9.0 * pseudo(cell["center_lat"], cell["center_lon"], "slope")
