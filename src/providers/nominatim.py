from __future__ import annotations

import time
from typing import Any

import requests

_USER_AGENT = "LucianoBuildingDemo/1.0 (weekend demo; contact: local)"
_last_request = 0.0


def geocode_address(address: str) -> dict[str, Any]:
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": _USER_AGENT}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    _last_request = time.time()
    data = resp.json()
    if not data:
        raise RuntimeError(f"Nominatim: no results for '{address}'")
    r0 = data[0]
    return {
        "address": address,
        "formatted_address": r0.get("display_name", address),
        "lat": float(r0["lat"]),
        "lng": float(r0["lon"]),
        "place_id": r0.get("place_id"),
        "source": "nominatim",
    }
