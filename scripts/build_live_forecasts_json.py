#!/usr/bin/env python3
"""Assemble per-country live forecast JSON into a single artifact file.

Reads results/live/<country>.json (produced by src/live_forecast.py),
adds a top-level envelope (schema version, generated_at, country list),
and writes webapp/_data/live_forecasts.json — which the publish step
copies into the MacroLab public artifact directory.

Schema (v1) — see autoresearch-macro/scripts/build_live_forecasts_json.py
docstring for canonical reference:

    {
      "schema_version": "1.0",
      "generated_at": "<ISO 8601 UTC>",
      "horizons": [1..12],
      "quantile_levels": [0.1, 0.25, 0.5, 0.75, 0.9],
      "history_months": 60,
      "countries": [
        {
          "country": "norway",
          "display_name": "Norway",
          "forecast_origin": "YYYY-MM-DD",
          "data_vintage": "YYYY-MM-DD",
          "best_config": {...},
          "targets": {
            "cpi": {
              "display_name": "...",
              "unit": "...",
              "history": [{"date": "YYYY-MM-DD", "value": ...}, ...],
              "models": {
                "chronos2_informed": {
                  "last_data_date": "YYYY-MM-DD",
                  "horizons": [
                    {"horizon": 1, "date": "...", "mean": ...,
                     "q10": ..., "q25": ..., "q50": ..., "q75": ..., "q90": ...},
                    ...
                  ]
                },
                "bvar": {... point only ...},
                "ets":  {... point only ...}
              }
            }, ...
          }
        }, ...
      ]
    }
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_ROOT / "results" / "live"
DEFAULT_OUTPUT = PROJECT_ROOT / "webapp" / "_data" / "live_forecasts.json"

SCHEMA_VERSION = "1.0"
COUNTRY_ORDER = ("norway", "canada", "sweden")
HORIZONS = list(range(1, 13))
QUANTILE_LEVELS = [0.1, 0.25, 0.5, 0.75, 0.9]
HISTORY_MONTHS = 60


def _iso_utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_country_payloads(live_dir: Path) -> list[dict[str, Any]]:
    """Load per-country JSON files in canonical order; skip missing ones."""
    payloads: list[dict[str, Any]] = []
    for country in COUNTRY_ORDER:
        path = live_dir / f"{country}.json"
        if not path.exists():
            print(f"  [skip] {path} not found")
            continue
        payloads.append(json.loads(path.read_text()))
    return payloads


def build_envelope(country_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso_utc_now(),
        "horizons": HORIZONS,
        "quantile_levels": QUANTILE_LEVELS,
        "history_months": HISTORY_MONTHS,
        "model_labels": {
            "chronos2_informed": "Chronos-2 (informed search)",
            "bvar": "BVAR (Minnesota prior)",
            "ets": "ETS (univariate)",
        },
        "countries": country_payloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-dir", type=Path, default=LIVE_DIR,
        help="Directory holding per-country JSON files",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Output path for the consolidated artifact JSON",
    )
    args = parser.parse_args()

    print(f"Reading per-country live forecasts from {args.live_dir}")
    payloads = load_country_payloads(args.live_dir)
    if not payloads:
        print("No country payloads found — nothing to write.")
        return 1

    envelope = build_envelope(payloads)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, indent=2))
    print(f"Wrote {args.output} ({len(payloads)} countries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
