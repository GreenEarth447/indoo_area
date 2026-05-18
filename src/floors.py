from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def estimate_floors_from_streetview(image_path: Path) -> dict[str, Any]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)
    h, w = img.shape[:2]
    x0, x1 = int(w * 0.2), int(w * 0.8)
    y0, y1 = int(h * 0.15), int(h * 0.85)
    roi = img[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    proj = np.mean(np.abs(sobel_y), axis=1)
    proj = cv2.GaussianBlur(proj.reshape(-1, 1), (1, 9), 0).flatten()
    proj = (proj - proj.min()) / (proj.max() - proj.min() + 1e-6)

    thresh = 0.45
    peaks: list[int] = []
    for i in range(1, len(proj) - 1):
        if proj[i] > thresh and proj[i] >= proj[i - 1] and proj[i] >= proj[i + 1]:
            if not peaks or i - peaks[-1] > 12:
                peaks.append(i)

    if len(peaks) >= 2:
        bands = len(peaks) - 1
        num_floors = max(1, min(bands, 60))
    else:
        num_floors = max(1, min(int(roi.shape[0] / 80), 40))

    profile_path = image_path.parent / f"{image_path.stem}_floor_profile.png"
    _save_profile(proj, peaks, profile_path)

    return {
        "num_floors": int(num_floors),
        "peaks_detected": len(peaks),
        "image": str(image_path),
        "profile_path": str(profile_path),
        "method": "streetview_facade_band_analysis",
    }


def _save_profile(proj: np.ndarray, peaks: list[int], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4, 6))
    ax.plot(proj, range(len(proj)))
    for p in peaks:
        ax.axhline(p, color="red", alpha=0.4, linewidth=0.8)
    ax.set_xlabel("Edge energy")
    ax.set_ylabel("Row (down)")
    ax.invert_yaxis()
    ax.set_title("Facade vertical profile")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def estimate_floors_from_set(streetview_images: list[dict[str, Any]]) -> dict[str, Any]:
    estimates = [estimate_floors_from_streetview(Path(s["path"])) for s in streetview_images]
    counts = [e["num_floors"] for e in estimates]
    num_floors = int(np.median(counts))
    return {
        "num_floors": max(1, num_floors),
        "per_heading": estimates,
        "fusion_note": "Median floor count across Street View headings",
    }


def apply_osm_levels_hint(floor_result: dict[str, Any], osm: dict[str, Any] | None) -> dict[str, Any]:
    if not osm:
        return floor_result
    levels = osm.get("levels_tag")
    if not levels:
        return floor_result
    try:
        osm_levels = int(float(str(levels).split(";")[0]))
    except ValueError:
        return floor_result
    sv = floor_result["num_floors"]
    fused = max(sv, osm_levels) if abs(sv - osm_levels) <= 2 else int(round(0.6 * sv + 0.4 * osm_levels))
    floor_result = dict(floor_result)
    floor_result["num_floors_fused"] = max(1, fused)
    floor_result["osm_levels"] = osm_levels
    floor_result["fusion_note"] = (
        f"Blended Street View ({sv}) with OSM building:levels ({osm_levels})"
    )
    return floor_result
