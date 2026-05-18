from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

_ESRI_TILE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
_OSM_TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def _lat_lng_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    x = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _fetch_tile(url_template: str, z: int, x: int, y: int) -> Image.Image:
    url = url_template.format(z=z, y=y, x=x)
    headers = {"User-Agent": "LucianoBuildingDemo/1.0"}
    resp = requests.get(url, timeout=45, headers=headers)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content)).convert("RGB")


def _stitch_tiles(
    lat: float,
    lng: float,
    url_template: str,
    *,
    zoom: int,
    size: int,
) -> Image.Image:
    cx, cy = _lat_lng_to_tile(lat, lng, zoom)
    tile_px = 256
    grid = 3
    canvas = Image.new("RGB", (grid * tile_px, grid * tile_px))
    ox = cx - grid // 2
    oy = cy - grid // 2
    for dy in range(grid):
        for dx in range(grid):
            tile = _fetch_tile(url_template, zoom, ox + dx, oy + dy)
            canvas.paste(tile, (dx * tile_px, dy * tile_px))
    w, h = canvas.size
    left = (w - size) // 2
    top = (h - size) // 2
    return canvas.crop((left, top, left + size, top + size))


def fetch_satellite_image(
    lat: float,
    lng: float,
    out_path: Path,
    *,
    zoom: int = 19,
    size: int = 640,
) -> tuple[Path, str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        img = _stitch_tiles(lat, lng, _ESRI_TILE, zoom=zoom, size=size)
        provider = "esri_world_imagery"
    except Exception:
        img = _stitch_tiles(lat, lng, _OSM_TILE, zoom=zoom, size=size)
        provider = "openstreetmap_tiles_fallback"
    img.save(out_path, "JPEG", quality=92)
    return out_path, provider
