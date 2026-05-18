from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
DATA_DIR = ROOT / "data"

DEFAULTS: dict[str, Any] = {
    "demo_addresses": [],
    "buildings_file": "buildings_demo.yaml",
    "data_mode": "google",
    "image_size": 640,
    "satellite_zoom": 19,
    "streetview_size": 640,
    "indoor_efficiency_factor": 0.88,
    "streetview_headings": [0, 90, 180, 270],
}


def load_demo_addresses(cfg: dict[str, Any]) -> list[str]:
    buildings_file = cfg.get("buildings_file")
    if buildings_file:
        path = ROOT / str(buildings_file)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            items = data.get("demo_addresses", [])
            if items and isinstance(items[0], dict):
                return [item["address"] for item in items if item.get("address")]
            return list(items)

    raw = cfg.get("demo_addresses") or []
    if raw and isinstance(raw[0], dict):
        return [item["address"] for item in raw if item.get("address")]
    if raw:
        return list(raw)
    return ["1 World Trade Center, New York, NY 10007"]


def load_config() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    cfg = dict(DEFAULTS)
    path = ROOT / "config.yaml"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            cfg.update(yaml.safe_load(f) or {})
    cfg["demo_addresses"] = load_demo_addresses(cfg)
    cfg["api_key"] = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    cfg["root"] = ROOT
    cfg["output_dir"] = OUTPUT_DIR
    cfg["data_dir"] = DATA_DIR
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return cfg
