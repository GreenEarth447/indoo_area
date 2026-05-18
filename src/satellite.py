from __future__ import annotations

from pathlib import Path

import requests


def fetch_satellite_image(
    lat: float,
    lng: float,
    api_key: str,
    out_path: Path,
    *,
    zoom: int = 19,
    size: int = 640,
    maptype: str = "satellite",
) -> Path:
    url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lng}",
        "zoom": zoom,
        "size": f"{size}x{size}",
        "maptype": maptype,
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    return out_path
