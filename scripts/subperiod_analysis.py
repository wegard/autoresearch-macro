"""Extract and display subperiod analysis from test-era results.

Prints formatted comparison tables for pre-COVID, COVID, and post-COVID
subperiods, and exports data as JSON for the webapp.

Usage:
    uv run python scripts/subperiod_analysis.py
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "test"
OUTPUT_DIR = PROJECT_ROOT / "webapp" / "_data"

METHODS = ["random_walk", "arima", "chronos2_zs", "chronos2_ft"]
METHOD_NAMES = {
    "random_walk": "Random Walk",
    "arima": "ARIMA",
    "chronos2_zs": "Chronos-2 (zero-shot)",
    "chronos2_ft": "Chronos-2 (agent-tuned)",
}

SUBPERIODS = {
    "full_test": "Full test (2016+)",
    "pre_covid": "Pre-COVID (2016-2019)",
    "covid": "COVID (2020-2021)",
    "post_covid": "Post-COVID (2022+)",
}

VARIABLES = ["cpi", "industrial_production", "retail_sales", "unemployment"]
HORIZONS = [1, 3, 6, 12]


def load_all_results() -> dict:
    """Load metrics.json from all test-era methods."""
    results = {}
    for method in METHODS:
        path = RESULTS_DIR / method / "metrics.json"
        if path.exists():
            results[method] = json.loads(path.read_text())
    return results


def print_subperiod_table(
    results: dict, subperiod: str, metric: str = "rmse"
) -> None:
    """Print a comparison table for one subperiod."""
    sp_label = SUBPERIODS.get(subperiod, subperiod)
    print(f"\n{'=' * 80}")
    print(f"  {sp_label} — {metric.upper()}")
    print(f"{'=' * 80}")

    # Header
    header = f"  {'Variable':>25s}  {'h':>3s}"
    for method in METHODS:
        header += f"  {METHOD_NAMES[method]:>22s}"
    print(header)
    print(f"  {'-' * (len(header) - 2)}")

    for var in VARIABLES:
        for h in HORIZONS:
            row = f"  {var.replace('_', ' '):>25s}  {h:>3d}"
            best_val = float("inf")
            vals = []
            for method in METHODS:
                sp_metrics = results.get(method, {}).get("subperiod_metrics", {})
                val = sp_metrics.get(subperiod, {}).get(var, {}).get(str(h), {}).get(metric)
                vals.append(val)
                if val is not None and val < best_val:
                    best_val = val
            for val in vals:
                if val is None:
                    row += f"  {'—':>22s}"
                elif abs(val - best_val) < 0.0001:
                    row += f"  {'*' + f'{val:.4f}':>22s}"
                else:
                    row += f"  {val:>22.4f}"
            print(row)
        print()


def export_subperiod_json(results: dict) -> None:
    """Export subperiod metrics as flat JSON for the webapp."""
    records = []
    for method in METHODS:
        sp_all = results.get(method, {}).get("subperiod_metrics", {})
        for sp_name, sp_metrics in sp_all.items():
            for var, horizons in sp_metrics.items():
                for h_str, metrics in horizons.items():
                    records.append({
                        "method": method,
                        "method_display": METHOD_NAMES[method],
                        "subperiod": sp_name,
                        "subperiod_display": SUBPERIODS.get(sp_name, sp_name),
                        "variable": var,
                        "horizon": int(h_str),
                        "rmse": metrics.get("rmse"),
                        "mae": metrics.get("mae"),
                        "mase": metrics.get("mase"),
                        "n_origins": metrics.get("n_origins"),
                    })

    output_path = OUTPUT_DIR / "subperiod_metrics.json"
    output_path.write_text(json.dumps(records, indent=2))
    print(f"\nExported {len(records)} records to {output_path}")


def main() -> None:
    results = load_all_results()
    if not results:
        print("No test-era results found. Run baselines and train.py on --era test first.")
        return

    print(f"Loaded results for: {', '.join(results.keys())}")

    for sp in ["pre_covid", "covid", "post_covid"]:
        print_subperiod_table(results, sp, metric="rmse")

    # Summary: average across variables for each subperiod
    print(f"\n{'=' * 80}")
    print(f"  SUMMARY — Average RMSE across targets")
    print(f"{'=' * 80}")
    for sp_name, sp_label in SUBPERIODS.items():
        if sp_name == "full_test":
            continue
        print(f"\n  {sp_label}:")
        header = f"    {'h':>3s}"
        for method in METHODS:
            header += f"  {METHOD_NAMES[method]:>22s}"
        print(header)
        for h in HORIZONS:
            row = f"    {h:>3d}"
            for method in METHODS:
                sp_metrics = results.get(method, {}).get("subperiod_metrics", {})
                vals = []
                for var in VARIABLES:
                    v = sp_metrics.get(sp_name, {}).get(var, {}).get(str(h), {}).get("rmse")
                    if v is not None:
                        vals.append(v)
                avg = sum(vals) / len(vals) if vals else float("nan")
                row += f"  {avg:>22.4f}"
            print(row)

    export_subperiod_json(results)


if __name__ == "__main__":
    main()
