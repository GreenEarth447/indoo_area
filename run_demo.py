#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.pipeline import _resolve_mode, run_building_pipeline
from src.visualize import write_summary_card


def _write_batch_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "address",
        "building_name",
        "footprint_sqm",
        "floor_count",
        "total_indoor_sqm_est",
        "footprint_source",
        "status",
        "result_path",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fuse Google Street View + satellite to estimate indoor sqm per floor."
    )
    parser.add_argument(
        "--address",
        "-a",
        action="append",
        help="Building address (repeatable). Defaults to buildings list in config.",
    )
    parser.add_argument(
        "--mode",
        choices=["google", "open"],
        default=None,
        help="Data source (default: google). Use 'open' only if you have no API key.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Process all buildings even if one fails (recommended for batch).",
    )
    parser.add_argument(
        "--list-config",
        action="store_true",
        help="Print configured demo addresses and exit.",
    )
    parser.add_argument(
        "--check-key",
        action="store_true",
        help="Test Google API key (Geocoding, Static Maps, Street View) and exit.",
    )
    args = parser.parse_args()
    cfg = load_config()
    if args.mode:
        cfg["data_mode"] = args.mode

    if args.check_key:
        from check_google_key import main as check_main

        return check_main()

    if args.list_config:
        for i, addr in enumerate(cfg["demo_addresses"], 1):
            print(f"{i:2}. {addr}")
        return 0

    addresses = args.address or cfg["demo_addresses"]
    try:
        mode = _resolve_mode(cfg)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    if mode == "google":
        print("Mode: GOOGLE Maps Platform")
        print("  Street View: panoramas around building, aimed at facade\n")
    else:
        print("Mode: OPEN (fallback — no Google key)\n")

    print(f"Batch: {len(addresses)} building(s)\n")

    batch_rows: list[dict] = []
    failed = 0

    for i, address in enumerate(addresses, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(addresses)}] {address}")
        print("=" * 60)
        try:
            result = run_building_pipeline(address, cfg)
            card = Path(result["result_path"]).parent / "summary.png"
            write_summary_card(result, card)
            fusion = result.get("fusion_summary", {})
            footprint = result.get("footprint", {})
            print(f"  Footprint: {footprint.get('footprint_sqm')} sqm ({fusion.get('footprint_source')})")
            print(f"  Floors: {fusion.get('floor_count')}")
            print(f"  Total indoor sqm (est.): {fusion.get('total_indoor_sqm_est')}")
            print(f"  Result: {result['result_path']}")
            batch_rows.append(
                {
                    "address": address,
                    "building_name": result.get("data_sources", {}).get("building_name") or "",
                    "footprint_sqm": footprint.get("footprint_sqm"),
                    "floor_count": fusion.get("floor_count"),
                    "total_indoor_sqm_est": fusion.get("total_indoor_sqm_est"),
                    "footprint_source": fusion.get("footprint_source"),
                    "status": "ok",
                    "result_path": result.get("result_path"),
                    "error": "",
                }
            )
        except Exception as exc:
            failed += 1
            print(f"  FAILED: {exc}")
            batch_rows.append(
                {
                    "address": address,
                    "building_name": "",
                    "footprint_sqm": "",
                    "floor_count": "",
                    "total_indoor_sqm_est": "",
                    "footprint_source": "",
                    "status": "failed",
                    "result_path": "",
                    "error": str(exc),
                }
            )
            if not args.continue_on_error:
                break

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(cfg["output_dir"])
    csv_path = out_dir / f"batch_summary_{ts}.csv"
    json_path = out_dir / f"batch_summary_{ts}.json"
    _write_batch_csv(batch_rows, csv_path)
    json_path.write_text(json.dumps(batch_rows, indent=2), encoding="utf-8")

    ok = sum(1 for r in batch_rows if r["status"] == "ok")
    print(f"\n{'='*60}")
    print(f"Done: {ok}/{len(addresses)} succeeded, {failed} failed")
    print(f"Batch CSV:  {csv_path}")
    print(f"Batch JSON: {json_path}")
    print(f"Per-building outputs: {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
