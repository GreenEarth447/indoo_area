from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

LABELS = ("roof", "facade", "vegetation", "shadow", "other")


def segment_and_classify(image_path: Path, out_dir: Path) -> dict[str, Any]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)
    h, w = img.shape[:2]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    pixels = lab.reshape(-1, 3).astype(np.float32)
    k = 5
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels_flat, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    labels_img = labels_flat.reshape(h, w)

    segments: list[dict[str, Any]] = []
    overlay = img.copy()
    for cluster_id in range(k):
        mask = (labels_img == cluster_id).astype(np.uint8) * 255
        area_px = int(cv2.countNonZero(mask))
        if area_px < 500:
            continue
        ys, xs = np.where(labels_img == cluster_id)
        mean_y = float(np.mean(ys)) / h
        bgr = lab.reshape(-1, 3)[labels_flat.flatten() == cluster_id]
        if len(bgr) == 0:
            continue
        a_mean = float(np.mean(bgr[:, 1]))
        label = _heuristic_label(mean_y, a_mean)
        color = _color_for_label(label)
        colored = np.zeros_like(img)
        colored[labels_img == cluster_id] = color
        overlay = cv2.addWeighted(overlay, 1.0, colored, 0.35, 0)
        segments.append(
            {
                "cluster_id": int(cluster_id),
                "label": label,
                "area_px": area_px,
                "area_fraction": round(area_px / (h * w), 4),
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    seg_path = out_dir / f"{image_path.stem}_segments.png"
    cv2.imwrite(str(seg_path), overlay)
    return {
        "source_image": str(image_path),
        "segmentation_path": str(seg_path),
        "segments": segments,
        "labels_used": list(LABELS),
        "method": "kmeans_heuristic",
    }


def _heuristic_label(mean_y_norm: float, a_mean: float) -> str:
    if mean_y_norm < 0.35:
        return "roof"
    if a_mean < 120:
        return "vegetation"
    if mean_y_norm > 0.75:
        return "shadow"
    if 0.35 <= mean_y_norm <= 0.75:
        return "facade"
    return "other"


def _color_for_label(label: str) -> list[int]:
    palette = {
        "roof": [0, 0, 255],
        "facade": [0, 255, 255],
        "vegetation": [0, 255, 0],
        "shadow": [80, 80, 80],
        "other": [255, 0, 255],
    }
    return palette.get(label, [200, 200, 200])
