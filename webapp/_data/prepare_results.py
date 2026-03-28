"""Prepare project data for the web dashboard.

Reads results, panel data, and search logs from the project and writes
JSON files that D3.js / Observable Plot can consume directly.

Usage:
    uv run python webapp/_data/prepare_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent


def prepare_combined_metrics() -> None:
    """Combine metrics from all evaluated methods into one JSON file."""
    validation_dir = RESULTS_DIR / "validation"
    if not validation_dir.exists():
        print("No validation results found, skipping metrics.")
        return

    combined: dict = {"methods": []}

    for method_dir in sorted(validation_dir.iterdir()):
        if not method_dir.is_dir():
            continue
        metrics_path = method_dir / "metrics.json"
        config_path = method_dir / "config.json"
        if not metrics_path.exists():
            continue

        metrics = json.loads(metrics_path.read_text())
        config = json.loads(config_path.read_text()) if config_path.exists() else {}

        entry = {
            "name": method_dir.name,
            "display_name": _display_name(method_dir.name),
            "category": _categorize(method_dir.name),
            "runtime_seconds": config.get("runtime_seconds", 0),
            "metrics": metrics.get("metrics", {}),
            "summary": metrics.get("summary", {}),
        }
        combined["methods"].append(entry)

    (OUTPUT_DIR / "combined_metrics.json").write_text(
        json.dumps(combined, indent=2)
    )
    print(f"Wrote combined_metrics.json ({len(combined['methods'])} methods)")


def prepare_panel_timeseries() -> None:
    """Export macro panel as JSON time series for D3."""
    parquet_path = DATA_DIR / "macro_panel.parquet"
    if not parquet_path.exists():
        print("No panel data found, skipping timeseries.")
        return

    df = pd.read_parquet(parquet_path)

    # Convert to records format: [{date, var1, var2, ...}]
    # Sample to monthly (already monthly, but ensure clean dates)
    records = []
    for date, row in df.iterrows():
        record = {"date": date.strftime("%Y-%m-%d")}
        for col in df.columns:
            val = row[col]
            record[col] = round(float(val), 4) if pd.notna(val) else None
        records.append(record)

    (OUTPUT_DIR / "panel_timeseries.json").write_text(
        json.dumps(records)
    )
    print(f"Wrote panel_timeseries.json ({len(records)} months, {len(df.columns)} variables)")


def prepare_variable_metadata() -> None:
    """Export variable metadata for the data page."""
    meta_path = DATA_DIR / "panel_meta.json"
    if not meta_path.exists():
        print("No panel metadata found, skipping.")
        return

    raw = json.loads(meta_path.read_text())

    variables = []
    for col in raw.get("columns", []):
        meta = raw.get("metadata", {}).get(col, {})
        lag = raw.get("publication_lags", {}).get(col, 30)
        first = raw.get("first_available", {}).get(col)

        variables.append({
            "name": col,
            "display_name": col.replace("_", " ").title(),
            "description": meta.get("description", ""),
            "source": meta.get("source", "unknown"),
            "publication_lag_days": lag,
            "first_available": first,
            "is_target": col in ["cpi", "industrial_production", "retail_sales", "unemployment"],
        })

    (OUTPUT_DIR / "variable_metadata.json").write_text(
        json.dumps(variables, indent=2)
    )
    print(f"Wrote variable_metadata.json ({len(variables)} variables)")


def prepare_search_trajectory() -> None:
    """Export search log as JSON array for the search trajectory chart."""
    log_path = RESULTS_DIR / "search_log.jsonl"
    if not log_path.exists():
        print("No search log found, skipping trajectory.")
        return

    iterations = []
    for line in log_path.read_text().strip().split("\n"):
        if line.strip():
            iterations.append(json.loads(line))

    (OUTPUT_DIR / "search_trajectory.json").write_text(
        json.dumps(iterations, indent=2)
    )
    print(f"Wrote search_trajectory.json ({len(iterations)} iterations)")


def _display_name(method_name: str) -> str:
    names = {
        "random_walk": "Random Walk",
        "seasonal_naive": "Seasonal Naive",
        "ar": "AR(p)",
        "arima": "ARIMA",
        "ets": "ETS",
        "chronos2_zs": "Chronos-2 (zero-shot)",
        "chronos2_ft": "Chronos-2 (fine-tuned)",
    }
    return names.get(method_name, method_name)


def _categorize(method_name: str) -> str:
    if method_name in ("random_walk", "seasonal_naive"):
        return "naive"
    if method_name in ("ar", "arima", "ets"):
        return "classical"
    if method_name.startswith("chronos"):
        return "foundation"
    return "other"


def main() -> None:
    print(f"Preparing data for web dashboard...")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Output dir: {OUTPUT_DIR}")
    print()

    prepare_combined_metrics()
    prepare_variable_metadata()
    prepare_panel_timeseries()
    prepare_search_trajectory()

    print("\nDone.")


if __name__ == "__main__":
    main()
