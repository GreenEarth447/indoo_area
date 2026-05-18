from __future__ import annotations

from typing import Any


def compute_indoor_areas(
    footprint_sqm: float,
    num_floors: int,
    efficiency_factor: float = 0.88,
) -> dict[str, Any]:
    if footprint_sqm <= 0 or num_floors < 1:
        return {
            "floors": [],
            "total_gross_sqm": 0.0,
            "total_indoor_sqm_est": 0.0,
            "method": "fused_footprint_x_floors",
        }

    gross_per_floor = footprint_sqm
    indoor_per_floor = round(gross_per_floor * efficiency_factor, 2)
    floors = []
    for f in range(1, num_floors + 1):
        floors.append(
            {
                "floor": f,
                "gross_sqm": round(gross_per_floor, 2),
                "indoor_sqm_est": indoor_per_floor,
            }
        )
    total_gross = round(gross_per_floor * num_floors, 2)
    total_indoor = round(indoor_per_floor * num_floors, 2)
    return {
        "floors": floors,
        "total_gross_sqm": total_gross,
        "total_indoor_sqm_est": total_indoor,
        "method": "fused_footprint_x_floors",
        "efficiency_factor": efficiency_factor,
        "assumption": "Exterior estimate: footprint x floors x efficiency factor",
    }
