from __future__ import annotations

import math


def meters_per_pixel(lat: float, zoom: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2**zoom)


def sqm_from_pixel_area(area_px: float, lat: float, zoom: int) -> float:
    mpp = meters_per_pixel(lat, zoom)
    return area_px * (mpp**2)
