from __future__ import annotations

import json
import os
import zlib
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from schemas import BoundingBox

from ..common import bbox_within_conus, imagery_size, safe_env_int
from ..http import decode_png_rows, http_get_bytes, http_post_form, http_post_json
from ..models import ImageryRaster


MAPBOX_STATIC_IMAGES_URL = "https://api.mapbox.com/styles/v1"
SENTINEL_TOKEN_URL = "https://services.sentinel-hub.com/oauth/token"
SENTINEL_PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"
USGS_EXPORT_URL = (
    "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export"
)


def fetch_imagery_raster(
    provider: str,
    bbox: BoundingBox,
) -> tuple[ImageryRaster | None, str, list[str]]:
    if provider == "none":
        return None, "not-requested", [
            "Imagery provider was not requested; land-cover features used deterministic fallbacks.",
        ]
    if provider == "usgs":
        return fetch_usgs_imagery(bbox)
    if provider == "mapbox":
        return fetch_mapbox_imagery(bbox)
    if provider == "sentinel":
        return fetch_sentinel_imagery(bbox)
    if provider == "google":
        if bbox_within_conus(bbox):
            raster, source, notes = fetch_usgs_imagery(bbox)
            return raster, source, [
                "Undocumented Google tile scraping is not used because it is not a supported Maps Platform integration.",
                *notes,
            ]
        return None, "google-unsupported-fallback", [
            "Undocumented Google tile scraping is not used because it is not a supported Maps Platform integration.",
            "Imagery features fell back because no alternate free imagery provider was available for this request.",
        ]
    return None, f"{provider}-unsupported-fallback", [
        f"Imagery provider '{provider}' is not wired for live retrieval; land-cover features used deterministic fallbacks.",
    ]


def fetch_usgs_imagery(bbox: BoundingBox) -> tuple[ImageryRaster | None, str, list[str]]:
    size = imagery_size()
    query = urlencode(
        {
            "bbox": f"{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}",
            "bboxSR": "4326",
            "imageSR": "4326",
            "size": f"{size},{size}",
            "format": "png32",
            "transparent": "false",
            "f": "image",
        }
    )
    url = f"{USGS_EXPORT_URL}?{query}"

    try:
        raw = http_get_bytes(url)
        width, height, rows = decode_png_rows(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, zlib.error, json.JSONDecodeError) as error:
        return None, "usgs-request-fallback", [
            f"USGS imagery could not be retrieved ({error.__class__.__name__}); imagery features used deterministic fallbacks.",
        ]

    notes = [
        f"USGS imagery retrieved at {width}x{height} resolution for land-cover sampling.",
    ]
    notes.append(
        "USGS imagery source composition varies by region; it should be treated as a live basemap input rather than assumed NAIP coverage."
    )

    return (
        ImageryRaster(
            provider="usgs",
            source="usgs-imagery-only",
            width=width,
            height=height,
            bbox=bbox,
            rows=rows,
        ),
        "usgs-imagery-only",
        notes,
    )


def fetch_mapbox_imagery(bbox: BoundingBox) -> tuple[ImageryRaster | None, str, list[str]]:
    token = os.getenv("MAPBOX_ACCESS_TOKEN")
    if not token:
        return None, "mapbox-missing-token-fallback", [
            "MAPBOX_ACCESS_TOKEN was not set, so imagery features used deterministic fallbacks.",
        ]

    owner = os.getenv("MAPBOX_STYLE_OWNER", "mapbox")
    style_id = os.getenv("MAPBOX_STYLE_ID", "satellite-streets-v12")
    size = imagery_size()
    bounds = f"[{bbox.min_lon},{bbox.min_lat},{bbox.max_lon},{bbox.max_lat}]"
    query = urlencode(
        {
            "access_token": token,
            "logo": "false",
            "attribution": "false",
        }
    )
    url = f"{MAPBOX_STATIC_IMAGES_URL}/{owner}/{style_id}/static/{bounds}/{size}x{size}?{query}"

    try:
        raw = http_get_bytes(url)
        width, height, rows = decode_png_rows(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, zlib.error, json.JSONDecodeError) as error:
        return None, "mapbox-request-fallback", [
            f"Mapbox imagery could not be retrieved ({error.__class__.__name__}); imagery features used deterministic fallbacks.",
        ]

    return (
        ImageryRaster(
            provider="mapbox",
            source=f"mapbox-static-images:{owner}/{style_id}",
            width=width,
            height=height,
            bbox=bbox,
            rows=rows,
        ),
        f"mapbox-static-images:{owner}/{style_id}",
        [f"Mapbox imagery retrieved at {width}x{height} resolution for land-cover sampling."],
    )


def fetch_sentinel_access_token() -> str:
    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("Missing Sentinel Hub credentials.")

    payload = json.loads(
        http_post_form(
            SENTINEL_TOKEN_URL,
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        ).decode("utf-8")
    )
    access_token = payload.get("access_token")
    if not access_token:
        raise ValueError("Sentinel Hub token response did not include an access token.")
    return access_token


def fetch_sentinel_imagery(bbox: BoundingBox) -> tuple[ImageryRaster | None, str, list[str]]:
    try:
        token = fetch_sentinel_access_token()
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        return None, "sentinel-auth-fallback", [
            f"Sentinel Hub authentication failed ({error.__class__.__name__}); imagery features used deterministic fallbacks.",
        ]

    size = imagery_size()
    end_date = date.today()
    lookback_days = safe_env_int("SENTINEL_LOOKBACK_DAYS", 120, 14, 365)
    start_date = end_date - timedelta(days=lookback_days)
    max_cloud_cover = safe_env_int("SENTINEL_MAX_CLOUD_COVER", 25, 0, 100)
    collection = os.getenv("SENTINEL_HUB_COLLECTION", "sentinel-2-l2a")
    evalscript = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "dataMask"],
    output: { bands: 4 }
  };
}

function evaluatePixel(sample) {
  return [
    Math.min(1, sample.B04 * 2.5),
    Math.min(1, sample.B03 * 2.5),
    Math.min(1, sample.B02 * 2.5),
    sample.dataMask
  ];
}
""".strip()

    request_payload = {
        "input": {
            "bounds": {
                "bbox": [bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat],
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                },
            },
            "data": [
                {
                    "type": collection,
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{start_date.isoformat()}T00:00:00Z",
                            "to": f"{end_date.isoformat()}T23:59:59Z",
                        },
                        "maxCloudCoverage": max_cloud_cover,
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": size,
            "height": size,
            "responses": [
                {
                    "identifier": "default",
                    "format": {"type": "image/png"},
                }
            ],
        },
        "evalscript": evalscript,
    }

    try:
        raw = http_post_json(
            SENTINEL_PROCESS_URL,
            request_payload,
            headers={"Authorization": f"Bearer {token}", "Accept": "image/png"},
        )
        width, height, rows = decode_png_rows(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, zlib.error) as error:
        return None, "sentinel-request-fallback", [
            f"Sentinel imagery could not be retrieved ({error.__class__.__name__}); imagery features used deterministic fallbacks.",
        ]

    return (
        ImageryRaster(
            provider="sentinel",
            source=f"sentinel-hub-process:{collection}",
            width=width,
            height=height,
            bbox=bbox,
            rows=rows,
        ),
        f"sentinel-hub-process:{collection}",
        [f"Sentinel imagery retrieved at {width}x{height} resolution for land-cover sampling."],
    )
