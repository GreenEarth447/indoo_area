from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2


def create_facade_proxy_from_satellite(satellite_path: Path, out_dir: Path) -> list[dict[str, Any]]:
    img = cv2.imread(str(satellite_path))
    if img is None:
        raise FileNotFoundError(satellite_path)
    h, w = img.shape[:2]
    x0, x1 = int(w * 0.35), int(w * 0.65)
    strip = img[:, x0:x1]
    strip = cv2.resize(strip, (640, 640), interpolation=cv2.INTER_LINEAR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "facade_proxy_from_satellite.jpg"
    cv2.imwrite(str(path), strip)
    return [
        {
            "path": str(path),
            "heading": 0,
            "source": "satellite_facade_proxy",
            "note": "satellite facade proxy",
        }
    ]
