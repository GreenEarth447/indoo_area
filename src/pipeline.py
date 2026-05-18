from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.floor_fusion import fuse_floor_estimates
from src.floors import estimate_floors_from_set
from src.footprint import resolve_footprint
from src.fusion import compute_indoor_areas
from src.geocoding import geocode_address as google_geocode
from src.providers.esri_satellite import fetch_satellite_image as fetch_esri_satellite
from src.providers.facade_proxy import create_facade_proxy_from_satellite
from src.providers.nominatim import geocode_address as nominatim_geocode
from src.satellite import fetch_satellite_image as fetch_google_satellite
from src.segmentation import segment_and_classify
from src.geo_bearing import polygon_centroid
from src.osm_footprint import fetch_osm_building_footprint
from src.streetview import fetch_streetview_set_facing_building


def run_building_pipeline(address: str, cfg: dict[str, Any]) -> dict[str, Any]:
    mode = _resolve_mode(cfg)
    if mode == "google":
        return _run_google(address, cfg)
    return _run_open(address, cfg)


def _resolve_mode(cfg: dict[str, Any]) -> str:
    mode = str(cfg.get("data_mode", "google")).lower()
    if mode == "auto":
        mode = "google"
    if mode not in ("google", "open"):
        raise ValueError(f"Unknown data_mode: {mode} (use google or open)")
    if mode == "google" and not cfg.get("api_key"):
        raise RuntimeError(
            "GOOGLE_MAPS_API_KEY is required. Copy .env.example to .env and add your key.\n"
            "Enable: Geocoding API, Maps Static API, Street View Static API.\n"
            "Or run with --mode open to use free data (no Google key)."
        )
    return mode


def _run_google(address: str, cfg: dict[str, Any]) -> dict[str, Any]:
    api_key = cfg["api_key"]
    slug = _slugify(address)
    out_base = Path(cfg["output_dir"]) / slug
    out_base.mkdir(parents=True, exist_ok=True)

    geo = google_geocode(address, api_key)
    lat, lng = geo["lat"], geo["lng"]

    osm_preview = fetch_osm_building_footprint(lat, lng)
    building_height_m = None
    building_name = None
    if osm_preview and osm_preview.get("coords"):
        lat, lng = polygon_centroid(osm_preview["coords"])
        building_height_m = osm_preview.get("height_m")
        building_name = osm_preview.get("name")

    zoom = int(cfg["satellite_zoom"])
    size = int(cfg["image_size"])

    sat_path = out_base / "satellite.jpg"
    fetch_google_satellite(lat, lng, api_key, sat_path, zoom=zoom, size=size)

    sv_dir = out_base / "streetview"
    streetviews = fetch_streetview_set_facing_building(
        lat,
        lng,
        api_key,
        sv_dir,
        building_height_m=building_height_m,
        size=int(cfg["streetview_size"]),
        max_views=int(cfg.get("streetview_max_views", 4)),
    )

    return _finalize(
        address=address,
        geo=geo,
        lat=lat,
        lng=lng,
        zoom=zoom,
        sat_path=sat_path,
        streetviews=streetviews,
        out_base=out_base,
        cfg=cfg,
        data_mode="google",
        osm_preview=osm_preview,
        building_name=building_name,
    )


def _run_open(address: str, cfg: dict[str, Any]) -> dict[str, Any]:
    slug = _slugify(address)
    out_base = Path(cfg["output_dir"]) / slug
    out_base.mkdir(parents=True, exist_ok=True)

    geo = nominatim_geocode(address)
    lat, lng = geo["lat"], geo["lng"]
    zoom = int(cfg["satellite_zoom"])
    size = int(cfg["image_size"])

    sat_path = out_base / "satellite.jpg"
    _, sat_provider = fetch_esri_satellite(lat, lng, sat_path, zoom=zoom, size=size)

    sv_dir = out_base / "facade_proxy"
    streetviews = create_facade_proxy_from_satellite(sat_path, sv_dir)

    return _finalize(
        address=address,
        geo=geo,
        lat=lat,
        lng=lng,
        zoom=zoom,
        sat_path=sat_path,
        streetviews=streetviews,
        out_base=out_base,
        cfg=cfg,
        data_mode="open",
        sat_provider=sat_provider,
    )


def _finalize(
    *,
    address: str,
    geo: dict[str, Any],
    lat: float,
    lng: float,
    zoom: int,
    sat_path: Path,
    streetviews: list[dict[str, Any]],
    out_base: Path,
    cfg: dict[str, Any],
    data_mode: str,
    sat_provider: str | None = None,
    osm_preview: dict[str, Any] | None = None,
    building_name: str | None = None,
) -> dict[str, Any]:
    footprint = resolve_footprint(lat, lng, sat_path, zoom)
    osm = footprint.get("osm") or osm_preview

    if data_mode == "open":
        sv_floors = estimate_floors_from_set(streetviews)
        floor_result = fuse_floor_estimates(sv_floors, osm)
    else:
        sv_floors = estimate_floors_from_set(streetviews)
        floor_result = fuse_floor_estimates(sv_floors, osm)

    num_floors = int(floor_result.get("num_floors_fused", floor_result["num_floors"]))

    areas = compute_indoor_areas(
        float(footprint.get("footprint_sqm", 0)),
        num_floors,
        efficiency_factor=float(cfg["indoor_efficiency_factor"]),
    )

    seg_sat = segment_and_classify(sat_path, out_base / "segments")
    best_sv = streetviews[0]["path"] if streetviews else str(sat_path)
    seg_sv = segment_and_classify(Path(best_sv), out_base / "segments")

    if data_mode == "open":
        sat_label = sat_provider or "esri_world_imagery"
        providers_note = (
            f"Open data (no Google key): Nominatim + {sat_label} + OSM footprint"
        )
    else:
        providers_note = "Google Maps Platform"

    result: dict[str, Any] = {
        "building_id": _slugify(address),
        "address": address,
        "formatted_address": geo.get("formatted_address", address),
        "lat": lat,
        "lng": lng,
        "data_mode": data_mode,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": {
            "provider_note": providers_note,
            "satellite_provider": sat_provider,
            "satellite_image": str(sat_path),
            "building_center_lat": lat,
            "building_center_lng": lng,
            "building_name": building_name,
            "streetview_images": streetviews,
            "streetview_method": "streetview_facing_building",
        },
        "footprint": footprint,
        "floors": floor_result,
        "indoor_areas": areas,
        "segmentation": {
            "satellite": seg_sat,
            "streetview_primary": seg_sv,
        },
        "fusion_summary": {
            "footprint_source": footprint.get("primary_source"),
            "floor_count": num_floors,
            "total_indoor_sqm_est": areas["total_indoor_sqm_est"],
            "notes": [
                providers_note,
                footprint.get("fusion_note"),
                floor_result.get("fusion_note"),
                areas.get("assumption"),
            ],
        },
    }

    json_path = out_base / "result.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["result_path"] = str(json_path)
    return result


def _slugify(address: str) -> str:
    keep = []
    for ch in address.lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " ,-":
            keep.append("_")
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:80] or "building"
