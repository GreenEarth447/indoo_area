from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.geo_utils import sqm_from_pixel_area
from src.osm_footprint import fetch_osm_building_footprint


def estimate_footprint_from_satellite(
    image_path: Path,
    lat: float,
    zoom: int,
) -> dict[str, Any]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    dilated = cv2.dilate(closed, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"source": "satellite_cv", "footprint_sqm": 0.0, "mask_path": None}

    cx, cy = w / 2, h / 2
    max_area_px = 0.12 * h * w
    min_area_px = 400
    scored: list[tuple[float, float, Any]] = []
    for c in contours:
        area_px = cv2.contourArea(c)
        if area_px < min_area_px or area_px > max_area_px:
            continue
        m = cv2.moments(c)
        if m["m00"] == 0:
            continue
        mx = m["m10"] / m["m00"]
        my = m["m01"] / m["m00"]
        dist = ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5
        scored.append((dist, area_px, c))

    if not scored:
        return {"source": "satellite_cv", "footprint_sqm": 0.0, "mask_path": None}

    scored.sort(key=lambda x: (x[0], -x[1]))
    _, best_area_px, best_contour = scored[0]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(mask, [best_contour], -1, 255, -1)
    mask_path = image_path.parent / f"{image_path.stem}_footprint_mask.png"
    cv2.imwrite(str(mask_path), mask)
    sqm = sqm_from_pixel_area(best_area_px, lat, zoom)
    return {
        "source": "satellite_cv",
        "footprint_sqm": round(sqm, 2),
        "footprint_area_px": best_area_px,
        "mask_path": str(mask_path),
    }


def resolve_footprint(
    lat: float,
    lng: float,
    satellite_path: Path,
    zoom: int,
) -> dict[str, Any]:
    osm = fetch_osm_building_footprint(lat, lng)
    sat = estimate_footprint_from_satellite(satellite_path, lat, zoom)
    osm_area = float(osm.get("footprint_sqm", 0)) if osm else 0.0
    sat_area = float(sat.get("footprint_sqm", 0))

    if osm and osm_area > 0 and osm_area < 150 and sat_area > 800:
        osm = {**osm, "rejected_reason": "tiny_polygon_near_pin"}
        osm_area = 0

    if osm and osm_area >= 150:
        return {
            "footprint_sqm": round(osm_area, 2),
            "primary_source": "osm",
            "osm": osm,
            "satellite_cv": sat,
            "fusion_note": (
                f"OSM building '{osm.get('name') or 'unnamed'}' "
                f"({osm_area:.0f} sqm footprint)"
            ),
        }
    return {
        "footprint_sqm": round(sat_area, 2),
        "primary_source": "satellite_cv",
        "osm": osm,
        "satellite_cv": sat,
        "fusion_note": "Satellite CV footprint (OSM unavailable or not trusted)",
    }
