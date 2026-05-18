from __future__ import annotations

from typing import Any

import numpy as np

from src.floors_osm import estimate_floors_from_osm


def fuse_floor_estimates(
    streetview_result: dict[str, Any],
    osm: dict[str, Any] | None,
) -> dict[str, Any]:
    sv_counts = [e["num_floors"] for e in streetview_result.get("per_heading", [])]
    sv_median = int(np.median(sv_counts)) if sv_counts else 1
    sv_max = max(sv_counts) if sv_counts else 1
    sv_min = min(sv_counts) if sv_counts else 1

    osm_result = estimate_floors_from_osm(osm)
    osm_floors = int(osm_result["num_floors"])
    osm_method = osm_result.get("method", "")
    height_m = (osm or {}).get("height_m")
    name = (osm or {}).get("name") or ""

    if osm_method in ("osm_building_levels", "osm_height", "osm_precomputed"):
        if osm_floors >= 15 or (height_m and height_m >= 80):
            fused = osm_floors
            note = f"OSM {osm_method}: {osm_floors} floors (SV median {sv_median})"
            if name:
                note += f" — {name}"
            return _pack(streetview_result, osm_result, fused, note, sv_median, sv_max, sv_min)

    if sv_counts and (sv_max - sv_min) >= 8 and osm_floors > sv_median:
        fused = max(osm_floors, sv_max)
        note = f"SV spread {sv_min}-{sv_max}; using {fused} floors"
        return _pack(streetview_result, osm_result, fused, note, sv_median, sv_max, sv_min)

    if osm and osm.get("levels_parsed"):
        fused = int(round(0.35 * sv_median + 0.65 * osm_floors))
        note = f"Blend SV {sv_median} + OSM levels {osm_floors}"
    elif osm_floors > sv_median * 1.5:
        fused = osm_floors
        note = f"OSM {osm_floors} floors (SV {sv_median})"
    else:
        fused = max(1, sv_median)
        note = f"Street View median: {sv_median} floors"

    return _pack(streetview_result, osm_result, max(1, fused), note, sv_median, sv_max, sv_min)


def _pack(
    sv: dict[str, Any],
    osm_r: dict[str, Any],
    fused: int,
    note: str,
    sv_median: int,
    sv_max: int,
    sv_min: int,
) -> dict[str, Any]:
    out = dict(sv)
    out["osm_floor_estimate"] = osm_r
    out["num_floors_fused"] = fused
    out["num_floors"] = fused
    out["streetview_median"] = sv_median
    out["streetview_max"] = sv_max
    out["streetview_min"] = sv_min
    out["fusion_note"] = note
    return out
