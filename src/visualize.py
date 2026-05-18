from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_summary_card(result: dict[str, Any], out_path: Path) -> Path:
    areas = result.get("indoor_areas", {})
    fusion = result.get("fusion_summary", {})
    floors = areas.get("floors", [])

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axis("off")
    lines = [
        f"Building: {result.get('formatted_address', result.get('address'))}",
        f"Footprint: {result.get('footprint', {}).get('footprint_sqm', '—')} sqm ({fusion.get('footprint_source')})",
        f"Floors: {fusion.get('floor_count', '—')}",
        f"Total indoor sqm (est.): {fusion.get('total_indoor_sqm_est', '—')}",
        "",
        "Per floor:",
    ]
    for fl in floors[:12]:
        lines.append(f"  Floor {fl['floor']}: {fl['indoor_sqm_est']} sqm")
    if len(floors) > 12:
        lines.append(f"  … +{len(floors) - 12} more floors")
    mode = result.get("data_mode", "google")
    method = (
        "Street View + satellite + OSM fusion"
        if mode == "google"
        else "Open data (Nominatim + OSM)"
    )
    lines.extend(["", f"Method: {method}"])
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", fontsize=11, family="monospace")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out_path
