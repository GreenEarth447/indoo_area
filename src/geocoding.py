from __future__ import annotations

from typing import Any

import requests

from src.google_errors import format_google_error


def geocode_address(address: str, api_key: str) -> dict[str, Any]:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise RuntimeError(
            format_google_error("Geocoding API", data) + f"\nAddress: {address}"
        )
    r0 = data["results"][0]
    loc = r0["geometry"]["location"]
    return {
        "address": address,
        "formatted_address": r0.get("formatted_address", address),
        "lat": loc["lat"],
        "lng": loc["lng"],
        "place_id": r0.get("place_id"),
        "location_type": r0["geometry"].get("location_type"),
        "bounds": r0["geometry"].get("bounds"),
    }
