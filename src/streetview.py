from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import requests

from src.geo_bearing import bearing_deg, haversine_m, offset_meters


def streetview_metadata(lat: float, lng: float, api_key: str) -> dict[str, Any]:
    url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {"location": f"{lat},{lng}", "key": api_key}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_streetview_image(
    lat: float,
    lng: float,
    api_key: str,
    out_path: Path,
    *,
    heading: float = 0,
    pitch: float = 0,
    fov: float = 90,
    size: int = 640,
) -> Path:
    url = "https://maps.googleapis.com/maps/api/streetview"
    params = {
        "size": f"{size}x{size}",
        "location": f"{lat},{lng}",
        "heading": heading,
        "pitch": pitch,
        "fov": fov,
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    return out_path


def _pitch_toward_top(distance_m: float, building_height_m: float | None) -> float:
    h = building_height_m or 80.0
    if distance_m < 5:
        distance_m = 5
    elev = math.degrees(math.atan2(h * 0.45, distance_m))
    return max(0.0, min(35.0, elev))


def _score_candidate(dist_m: float, pano_dist_to_target: float) -> float:
    ideal = 75.0
    return 1000.0 / (1.0 + abs(pano_dist_to_target - ideal) / 25.0) + dist_m * 0.01


def find_streetview_views_facing_building(
    building_lat: float,
    building_lng: float,
    api_key: str,
    *,
    building_height_m: float | None = None,
    search_distances_m: tuple[float, ...] = (40, 65, 90, 120, 150),
    search_bearings_deg: tuple[float, ...] = tuple(range(0, 360, 30)),
    max_views: int = 4,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_panos: set[str] = set()

    for dist in search_distances_m:
        for bearing in search_bearings_deg:
            probe_lat, probe_lng = offset_meters(building_lat, building_lng, dist, bearing)
            try:
                meta = streetview_metadata(probe_lat, probe_lng, api_key)
            except Exception:
                continue
            if meta.get("status") != "OK":
                continue

            loc = meta.get("location", {})
            pano_lat = loc.get("lat", probe_lat)
            pano_lng = loc.get("lng", probe_lng)
            pano_id = meta.get("pano_id", "")
            if pano_id and pano_id in seen_panos:
                continue

            dist_to_building = haversine_m(pano_lat, pano_lng, building_lat, building_lng)
            if dist_to_building < 15 or dist_to_building > 200:
                continue

            heading = bearing_deg(pano_lat, pano_lng, building_lat, building_lng)
            pitch = _pitch_toward_top(dist_to_building, building_height_m)

            candidates.append(
                {
                    "pano_lat": pano_lat,
                    "pano_lng": pano_lng,
                    "pano_id": pano_id,
                    "heading": round(heading, 1),
                    "pitch": round(pitch, 1),
                    "dist_to_building_m": round(dist_to_building, 1),
                    "probe_bearing_deg": bearing,
                    "probe_distance_m": dist,
                    "date": meta.get("date"),
                    "score": _score_candidate(dist, dist_to_building),
                }
            )
            if pano_id:
                seen_panos.add(pano_id)

    if not candidates:
        raise RuntimeError(
            f"No Street View panoramas near ({building_lat}, {building_lng})"
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)

    selected: list[dict[str, Any]] = []
    used_positions: list[tuple[float, float]] = []
    for c in candidates:
        pos = (c["pano_lat"], c["pano_lng"])
        if any(haversine_m(pos[0], pos[1], u[0], u[1]) < 25 for u in used_positions):
            continue
        selected.append(c)
        used_positions.append(pos)
        if len(selected) >= max_views:
            break

    if not selected:
        selected = candidates[:max_views]

    return selected


def fetch_streetview_set_facing_building(
    building_lat: float,
    building_lng: float,
    api_key: str,
    out_dir: Path,
    *,
    building_height_m: float | None = None,
    size: int = 640,
    max_views: int = 4,
) -> list[dict[str, Any]]:
    views = find_streetview_views_facing_building(
        building_lat,
        building_lng,
        api_key,
        building_height_m=building_height_m,
        max_views=max_views,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for i, v in enumerate(views):
        path = out_dir / f"streetview_facade_{i:02d}_h{int(v['heading']):03d}.jpg"
        fetch_streetview_image(
            v["pano_lat"],
            v["pano_lng"],
            api_key,
            path,
            heading=v["heading"],
            pitch=v["pitch"],
            size=size,
        )
        results.append(
            {
                "path": str(path),
                "heading": v["heading"],
                "pitch": v["pitch"],
                "pano_lat": v["pano_lat"],
                "pano_lng": v["pano_lng"],
                "pano_id": v["pano_id"],
                "date": v.get("date"),
                "dist_to_building_m": v["dist_to_building_m"],
                "method": "streetview_facing_building",
            }
        )

    return results


def fetch_streetview_set(
    lat: float,
    lng: float,
    api_key: str,
    out_dir: Path,
    headings: list[float],
    *,
    size: int = 640,
    building_height_m: float | None = None,
) -> list[dict[str, Any]]:
    return fetch_streetview_set_facing_building(
        lat,
        lng,
        api_key,
        out_dir,
        building_height_m=building_height_m,
        size=size,
        max_views=max(4, len(headings)),
    )
