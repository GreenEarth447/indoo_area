from __future__ import annotations

from typing import Any

from src.osm_footprint import floors_from_height, parse_height_m, parse_levels


def estimate_floors_from_osm(osm: dict[str, Any] | None) -> dict[str, Any]:
    if not osm:
        return {
            "num_floors": 1,
            "method": "osm_default",
            "fusion_note": "No OSM building; defaulting to 1 floor",
        }

    levels = osm.get("levels_parsed") or parse_levels(
        {"building:levels": osm.get("levels_tag") or "", "levels": ""}
    )
    if levels:
        return {
            "num_floors": levels,
            "method": "osm_building_levels",
            "osm_levels": levels,
            "fusion_note": f"OSM building:levels={levels}",
        }

    height_m = osm.get("height_m")
    if height_m is None and isinstance(osm.get("tags"), dict):
        height_m = parse_height_m(osm["tags"])

    if height_m and height_m > 0:
        n = floors_from_height(height_m)
        return {
            "num_floors": n,
            "method": "osm_height",
            "height_m": height_m,
            "fusion_note": f"OSM height {height_m:.0f}m -> {n} floors",
        }

    pre = osm.get("floors_estimated")
    if pre:
        return {
            "num_floors": int(pre),
            "method": "osm_precomputed",
            "fusion_note": f"OSM estimated {pre} floors",
        }

    btype = (osm.get("building_type") or "").lower()
    if btype in ("commercial", "office", "skyscraper", "hotel"):
        return {
            "num_floors": 10,
            "method": "osm_heuristic",
            "fusion_note": f"OSM type {btype}",
        }

    return {
        "num_floors": 1,
        "method": "osm_default",
        "fusion_note": "OSM polygon, no height/levels",
    }
