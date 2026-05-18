from __future__ import annotations

import math
import re
from typing import Any

import requests

_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
_HEADERS = {"User-Agent": "LucianoBuildingDemo/1.0"}
_FLOOR_HEIGHT_M = 3.8


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _ring_area_sqm(coords: list[list[float]]) -> float:
    if len(coords) < 3:
        return 0.0
    ring = coords[:]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    lat0 = sum(p[1] for p in ring) / len(ring)
    cos_lat = math.cos(math.radians(lat0))
    xy = [(p[0] * cos_lat * 111320.0, p[1] * 110540.0) for p in ring]
    area = 0.0
    for i in range(len(xy) - 1):
        x1, y1 = xy[i]
        x2, y2 = xy[i + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def parse_height_m(tags: dict[str, str]) -> float | None:
    raw = tags.get("height") or tags.get("building:height") or ""
    if not raw:
        return None
    s = str(raw).lower().strip()
    m = re.search(r"([\d.]+)", s)
    if not m:
        return None
    val = float(m.group(1))
    if "ft" in s or "feet" in s or "'" in s:
        val *= 0.3048
    return val


def parse_levels(tags: dict[str, str]) -> int | None:
    raw = tags.get("building:levels") or tags.get("levels") or ""
    if not raw:
        return None
    try:
        return max(1, int(float(str(raw).split(";")[0].split(",")[0])))
    except ValueError:
        return None


def floors_from_height(height_m: float) -> int:
    return max(1, int(round(height_m / _FLOOR_HEIGHT_M)))


def _run_overpass(query: str) -> dict[str, Any] | None:
    for url in _OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(
                url, data={"data": query}, headers=_HEADERS, timeout=90
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            continue
    return None


def _way_to_candidate(
    way: dict[str, Any], nodes: dict[int, tuple[float, float]], lat: float, lng: float
) -> dict[str, Any] | None:
    nds = way.get("nodes", [])
    if len(nds) < 3:
        return None
    coords = [[nodes[nid][0], nodes[nid][1]] for nid in nds if nid in nodes]
    if len(coords) < 3:
        return None
    area = _ring_area_sqm(coords)
    if area < 25:
        return None
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    dist = _haversine_m(lat, lng, cy, cx)
    tags = way.get("tags", {})
    height_m = parse_height_m(tags)
    levels = parse_levels(tags)
    floors_est = levels or (floors_from_height(height_m) if height_m else None)
    name = tags.get("name") or tags.get("building:name") or ""
    return {
        "source": "osm",
        "footprint_sqm": area,
        "distance_m": dist,
        "building_type": tags.get("building"),
        "name": name,
        "levels_tag": tags.get("building:levels"),
        "height_m": height_m,
        "levels_parsed": levels,
        "floors_estimated": floors_est,
        "coords": coords,
        "osm_id": way.get("id"),
    }


def _score_candidate(c: dict[str, Any], max_dist_m: float) -> float:
    if c["distance_m"] > max_dist_m:
        return -1.0
    dist = c["distance_m"]
    area = c["footprint_sqm"]
    floors = c.get("floors_estimated") or 0
    height = c.get("height_m") or 0.0
    name = (c.get("name") or "").lower()
    score = area / (1.0 + dist / 40.0)
    score += floors * 80
    score += height * 1.5
    if name and any(k in name for k in ("tower", "trade", "center", "centre", "plaza")):
        score += 500
    if c.get("building_type") in ("commercial", "office", "skyscraper", "yes"):
        score += 100
    return score


def fetch_osm_building_footprint(
    lat: float, lng: float, radius_m: float = 250
) -> dict[str, Any] | None:
    query = f"""[out:json][timeout:60];
(
  way["building"](around:{radius_m},{lat},{lng});
);
out body;
>;
out skel qt;"""
    data = _run_overpass(query)
    if not data:
        return None

    nodes = {e["id"]: (e["lon"], e["lat"]) for e in data.get("elements", []) if e["type"] == "node"}
    ways = [e for e in data.get("elements", []) if e["type"] == "way" and "building" in e.get("tags", {})]

    candidates: list[dict[str, Any]] = []
    for way in ways:
        c = _way_to_candidate(way, nodes, lat, lng)
        if c:
            candidates.append(c)

    if not candidates:
        return None

    max_dist = min(radius_m, 200.0)
    scored = [(c, _score_candidate(c, max_dist)) for c in candidates]
    scored = [(c, s) for c, s in scored if s >= 0]
    if not scored:
        scored = [(c, _score_candidate(c, radius_m * 2)) for c in candidates]

    best, best_score = max(scored, key=lambda x: x[1])
    best["selection_score"] = best_score
    best["candidates_considered"] = len(candidates)
    return best
