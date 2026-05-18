#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import requests

from src.config import load_config
from src.google_errors import format_google_error

REQUIRED_APIS: list[dict[str, str]] = [
    {
        "name": "Geocoding API",
        "service_id": "geocoding-backend.googleapis.com",
        "enable_url": "https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com",
        "used_for": "Address to lat/lng",
    },
    {
        "name": "Maps Static API",
        "service_id": "static-maps-backend.googleapis.com",
        "enable_url": "https://console.cloud.google.com/apis/library/static-maps-backend.googleapis.com",
        "used_for": "Satellite images",
    },
    {
        "name": "Street View Static API",
        "service_id": "street-view-image-backend.googleapis.com",
        "enable_url": "https://console.cloud.google.com/apis/library/street-view-image-backend.googleapis.com",
        "used_for": "Street View + metadata",
    },
]

BILLING_URL = "https://console.cloud.google.com/billing"
CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"


def _print_required_apis() -> None:
    print("Required APIs:\n")
    for i, api in enumerate(REQUIRED_APIS, 1):
        print(f"  {i}. {api['name']}")
        print(f"     {api['enable_url']}\n")
    print(f"  Billing: {BILLING_URL}")
    print(f"  Keys:    {CREDENTIALS_URL}\n")


def _test_geocoding(key: str) -> tuple[bool, str]:
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": "New York, NY", "key": key},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") == "OK":
        return True, "OK"
    return False, format_google_error("Geocoding API", data)


def _test_maps_static(key: str) -> tuple[bool, str]:
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/staticmap",
        params={
            "center": "40.7128,-74.0060",
            "zoom": 15,
            "size": "100x100",
            "maptype": "satellite",
            "key": key,
        },
        timeout=30,
    )
    if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
        return True, "OK"
    try:
        data = resp.json()
    except Exception:
        data = {"status": "REQUEST_DENIED", "error_message": resp.text[:300]}
    return False, format_google_error("Maps Static API", data)


def _test_streetview_metadata(key: str) -> tuple[bool, str]:
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/streetview/metadata",
        params={"location": "40.7128,-74.0060", "key": key},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") == "OK":
        return True, "OK"
    return False, format_google_error("Street View Static API", data)


def _test_streetview_image(key: str) -> tuple[bool, str]:
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/streetview",
        params={"size": "100x100", "location": "40.7128,-74.0060", "key": key},
        timeout=30,
    )
    if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
        return True, "OK"
    try:
        data = resp.json()
    except Exception:
        data = {"status": "REQUEST_DENIED", "error_message": resp.text[:300]}
    return False, format_google_error("Street View Static API", data)


API_TESTS: list[tuple[str, str, Callable[[str], tuple[bool, str]]]] = [
    ("Geocoding API", "geocoding-backend.googleapis.com", _test_geocoding),
    ("Maps Static API", "static-maps-backend.googleapis.com", _test_maps_static),
    ("Street View Static API", "street-view-image-backend.googleapis.com", _test_streetview_metadata),
    ("Street View Static API", "street-view-image-backend.googleapis.com", _test_streetview_image),
]


def main() -> int:
    _print_required_apis()

    cfg = load_config()
    key = cfg.get("api_key", "")
    if not key:
        print("ERROR: Set GOOGLE_MAPS_API_KEY in .env")
        return 1

    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "(too short?)"
    print("=" * 50)
    print(f"Testing key: {masked}\n")

    results: dict[str, bool] = {api["name"]: True for api in REQUIRED_APIS}

    for api_name, service_id, test_fn in API_TESTS:
        print(f"--- {api_name} [{service_id}] ---")
        try:
            ok, msg = test_fn(key)
        except requests.RequestException as exc:
            ok, msg = False, f"Network error: {exc}"

        if ok:
            print("  Status: OK")
        else:
            print(f"  Status: FAIL\n{msg}")
            results[api_name] = False
        print()

    print("=" * 50)
    print("Summary:\n")
    all_ok = True
    for api in REQUIRED_APIS:
        name = api["name"]
        passed = results.get(name, False)
        print(f"  [{'OK' if passed else 'X'}] {name}")
        if not passed:
            print(f"       {api['enable_url']}")
            all_ok = False

    print()
    if all_ok:
        print("All checks passed.")
        return 0

    geo_ok = results.get("Geocoding API", False)
    others_fail = not results.get("Maps Static API", True) or not results.get(
        "Street View Static API", True
    )
    if geo_ok and others_fail:
        print("Geocoding OK; Static/Street View blocked — check key API restrictions:")
        print(f"  {CREDENTIALS_URL}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
