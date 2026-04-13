"""Cross-check paper table values against result files.

Reads metrics.json from results/{era}/{method}/ and compares against
hard-coded values extracted from paper/main.tex tables. Outputs a
discrepancy report.

Usage:
    uv run python audit/cross_check_paper.py
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
REPORT_PATH = PROJECT_ROOT / "audit" / "discrepancy_report.md"


def load_summary(era: str, method: str) -> dict[str, dict[str, float]]:
    """Load summary metrics from results/{era}/{method}/metrics.json."""
    path = RESULTS_DIR / era / method / "metrics.json"
    with open(path) as f:
        data = json.load(f)
    return data["summary"]


def load_per_variable(era: str, method: str) -> dict[str, dict[str, dict[str, float]]]:
    """Load per-variable metrics from results/{era}/{method}/metrics.json."""
    path = RESULTS_DIR / era / method / "metrics.json"
    with open(path) as f:
        data = json.load(f)
    return data["metrics"]


def load_subperiod(era: str, method: str) -> dict:
    """Load subperiod metrics."""
    path = RESULTS_DIR / era / method / "metrics.json"
    with open(path) as f:
        data = json.load(f)
    return data.get("subperiod_metrics", {})


# ---- Paper table values (extracted from main.tex) ----

# Table: tab:validation — validation era avg MASE by method
PAPER_VALIDATION_MASE: dict[str, dict[str, float]] = {
    "random_walk":  {"1": 1.000, "3": 1.000, "6": 1.000, "12": 1.000},
    "arima":        {"1": 0.930, "3": 0.983, "6": 0.978, "12": 1.000},
    "ets":          {"1": 0.964, "3": 1.002, "6": 1.013, "12": 1.043},
    "var":          {"1": 1.000, "3": 1.063, "6": 1.119, "12": 1.133},
    "factor":       {"1": 1.290, "3": 1.341, "6": 1.520, "12": 2.060},
    "chronos2_zs":  {"1": 0.960, "3": 1.008, "6": 1.016, "12": 1.012},
}

# Table: tab:test — test era avg MASE by method
PAPER_TEST_MASE: dict[str, dict[str, float]] = {
    "random_walk":  {"1": 1.000, "3": 1.000, "6": 1.000, "12": 1.000},
    "arima":        {"1": 0.977, "3": 0.992, "6": 1.032, "12": 1.029},
    "var":          {"1": 0.979, "3": 1.075, "6": 1.175, "12": 1.202},
    "factor":       {"1": 1.192, "3": 1.170, "6": 1.260, "12": 1.377},
    "chronos2_zs":  {"1": 0.984, "3": 0.981, "6": 0.997, "12": 1.021},
    "chronos2_ft":  {"1": 1.011, "3": 1.025, "6": 1.085, "12": 1.205},
}

# Table: tab:subperiods — avg RMSE across targets
PAPER_SUBPERIOD_RMSE: dict[str, dict[str, dict[str, float]]] = {
    "pre_covid": {
        "random_walk":  {"1": 0.966, "3": 1.138, "6": 1.836, "12": 2.655},
        "arima":        {"1": 0.897, "3": 1.118, "6": 1.836, "12": 2.618},
        "chronos2_zs":  {"1": 0.862, "3": 1.033, "6": 1.773, "12": 2.633},
        "chronos2_ft":  {"1": 0.882, "3": 1.081, "6": 1.844, "12": 2.739},
    },
    "covid": {
        "random_walk":  {"1": 2.328, "3": 2.921, "6": 3.149, "12": 3.411},
        "arima":        {"1": 2.491, "3": 3.045, "6": 3.609, "12": 4.130},
        "chronos2_zs":  {"1": 2.519, "3": 3.008, "6": 3.495, "12": 4.003},
        "chronos2_ft":  {"1": 2.466, "3": 3.086, "6": 3.605, "12": 4.234},
    },
    "post_covid": {
        "random_walk":  {"1": 0.963, "3": 1.207, "6": 1.374, "12": 1.694},
        "arima":        {"1": 0.900, "3": 1.118, "6": 1.326, "12": 1.645},
        "chronos2_zs":  {"1": 0.953, "3": 1.183, "6": 1.334, "12": 1.734},
        "chronos2_ft":  {"1": 1.023, "3": 1.324, "6": 1.641, "12": 3.011},
    },
}

# Table: tab:per_variable_test — per-variable MASE, test era
PAPER_PER_VARIABLE_TEST_MASE: dict[str, dict[str, dict[str, float]]] = {
    "cpi": {
        "random_walk":  {"1": 1.000, "3": 1.000, "6": 1.000, "12": 1.000},
        "arima":        {"1": 1.019, "3": 1.015, "6": 0.996, "12": 0.998},
        "var":          {"1": 1.053, "3": 1.212, "6": 1.270, "12": 1.084},
        "factor":       {"1": 1.372, "3": 1.320, "6": 1.286, "12": 1.108},
        "chronos2_zs":  {"1": 1.024, "3": 1.016, "6": 0.992, "12": 0.956},
        "chronos2_ft":  {"1": 1.026, "3": 1.055, "6": 1.087, "12": 1.062},
    },
    "industrial_production": {
        "random_walk":  {"1": 1.000, "3": 1.000, "6": 1.000, "12": 1.000},
        "arima":        {"1": 1.043, "3": 1.007, "6": 1.067, "12": 1.057},
        "var":          {"1": 0.978, "3": 0.980, "6": 1.025, "12": 1.221},
        "factor":       {"1": 1.184, "3": 1.091, "6": 1.186, "12": 1.589},
        "chronos2_zs":  {"1": 1.024, "3": 0.981, "6": 0.974, "12": 1.048},
        "chronos2_ft":  {"1": 1.115, "3": 1.093, "6": 1.170, "12": 1.435},
    },
    "retail_sales": {
        "random_walk":  {"1": 1.000, "3": 1.000, "6": 1.000, "12": 1.000},
        "arima":        {"1": 0.971, "3": 1.003, "6": 1.069, "12": 1.069},
        "var":          {"1": 1.001, "3": 1.054, "6": 1.212, "12": 1.278},
        "factor":       {"1": 1.140, "3": 1.086, "6": 1.167, "12": 1.323},
        "chronos2_zs":  {"1": 0.993, "3": 0.977, "6": 1.036, "12": 1.102},
        "chronos2_ft":  {"1": 1.022, "3": 1.027, "6": 1.108, "12": 1.320},
    },
    "unemployment": {
        "random_walk":  {"1": 1.000, "3": 1.000, "6": 1.000, "12": 1.000},
        "arima":        {"1": 0.876, "3": 0.941, "6": 0.998, "12": 0.994},
        "var":          {"1": 0.884, "3": 1.052, "6": 1.194, "12": 1.224},
        "factor":       {"1": 1.072, "3": 1.182, "6": 1.400, "12": 1.487},
        "chronos2_zs":  {"1": 0.896, "3": 0.950, "6": 0.988, "12": 0.978},
        "chronos2_ft":  {"1": 0.880, "3": 0.924, "6": 0.977, "12": 1.003},
    },
}

# Table: tab:ablation — avg MASE across targets AND horizons
PAPER_ABLATION: dict[str, dict[str, float]] = {
    "Zero-shot baseline":      {"validation": 0.999, "test": 0.996},
    "+ context_length = 96":   {"validation": 0.968, "test": 1.001},
    "+ brent_crude":           {"validation": 0.963, "test": 1.005},
    "+ policy_rate":           {"validation": 0.951, "test": 1.046},
    "+ us_cpi":                {"validation": 0.941, "test": 1.064},
    "+ nok_eur":               {"validation": 0.944, "test": 1.080},
    "+ LoRA fine-tune":        {"validation": 0.943, "test": 1.081},
}


def compare_value(paper: float, result: float, tol: float = 0.0015) -> tuple[str, float]:
    """Compare paper value to result file value. Returns (status, diff)."""
    diff = abs(paper - result)
    if diff < 1e-9:
        return "EXACT", diff
    elif diff <= tol:
        return "OK (rounding)", diff
    else:
        return "MISMATCH", diff


def run_audit() -> str:
    """Run the full audit and return the report as markdown."""
    lines: list[str] = []
    lines.append("# Audit Report: Paper vs Result Files\n")
    lines.append("Generated automatically by `audit/cross_check_paper.py`.\n")

    mismatches: list[str] = []
    total_checks = 0
    exact_matches = 0
    rounding_matches = 0
    mismatch_count = 0

    # --- 1. Validation MASE table ---
    lines.append("## 1. Validation Era MASE (tab:validation)\n")
    lines.append("| Method | Horizon | Paper | Result | Status | Diff |")
    lines.append("|--------|---------|-------|--------|--------|------|")

    for method, horizons in PAPER_VALIDATION_MASE.items():
        summary = load_summary("validation", method)
        for h, paper_val in horizons.items():
            result_val = round(summary[h]["avg_mase"], 3)
            status, diff = compare_value(paper_val, result_val)
            total_checks += 1
            if status == "EXACT":
                exact_matches += 1
            elif status == "OK (rounding)":
                rounding_matches += 1
            else:
                mismatch_count += 1
                mismatches.append(f"Validation {method} h={h}: paper={paper_val}, result={result_val}")
            lines.append(f"| {method} | h={h} | {paper_val:.3f} | {result_val:.3f} | {status} | {diff:.4f} |")

    # --- 2. Test MASE table ---
    lines.append("\n## 2. Test Era MASE (tab:test)\n")
    lines.append("| Method | Horizon | Paper | Result | Status | Diff |")
    lines.append("|--------|---------|-------|--------|--------|------|")

    for method, horizons in PAPER_TEST_MASE.items():
        summary = load_summary("test", method)
        for h, paper_val in horizons.items():
            result_val = round(summary[h]["avg_mase"], 3)
            status, diff = compare_value(paper_val, result_val)
            total_checks += 1
            if status == "EXACT":
                exact_matches += 1
            elif status == "OK (rounding)":
                rounding_matches += 1
            else:
                mismatch_count += 1
                mismatches.append(f"Test {method} h={h}: paper={paper_val}, result={result_val}")
            lines.append(f"| {method} | h={h} | {paper_val:.3f} | {result_val:.3f} | {status} | {diff:.4f} |")

    # --- 3. Subperiod RMSE table ---
    lines.append("\n## 3. Subperiod RMSE (tab:subperiods)\n")
    lines.append("| Subperiod | Method | Horizon | Paper | Result | Status | Diff |")
    lines.append("|-----------|--------|---------|-------|--------|--------|------|")

    for subperiod, methods in PAPER_SUBPERIOD_RMSE.items():
        for method, horizons in methods.items():
            sub_metrics = load_subperiod("test", method)
            if subperiod not in sub_metrics:
                for h, paper_val in horizons.items():
                    total_checks += 1
                    mismatch_count += 1
                    mismatches.append(f"Subperiod {subperiod} {method} h={h}: NO DATA")
                    lines.append(f"| {subperiod} | {method} | h={h} | {paper_val:.3f} | N/A | NO DATA | --- |")
                continue
            sub_data = sub_metrics[subperiod]
            # Compute avg RMSE across targets
            targets = ["cpi", "industrial_production", "retail_sales", "unemployment"]
            for h, paper_val in horizons.items():
                rmse_vals = [sub_data[t][h]["rmse"] for t in targets if t in sub_data]
                result_val = round(sum(rmse_vals) / len(rmse_vals), 3)
                status, diff = compare_value(paper_val, result_val)
                total_checks += 1
                if status == "EXACT":
                    exact_matches += 1
                elif status == "OK (rounding)":
                    rounding_matches += 1
                else:
                    mismatch_count += 1
                    mismatches.append(f"Subperiod {subperiod} {method} h={h}: paper={paper_val}, result={result_val}")
                lines.append(f"| {subperiod} | {method} | h={h} | {paper_val:.3f} | {result_val:.3f} | {status} | {diff:.4f} |")

    # --- 4. Per-variable test MASE ---
    lines.append("\n## 4. Per-Variable Test MASE (tab:per_variable_test)\n")
    lines.append("| Variable | Method | Horizon | Paper | Result | Status | Diff |")
    lines.append("|----------|--------|---------|-------|--------|--------|------|")

    for variable, methods in PAPER_PER_VARIABLE_TEST_MASE.items():
        for method, horizons in methods.items():
            per_var = load_per_variable("test", method)
            for h, paper_val in horizons.items():
                result_val = round(per_var[variable][h]["mase"], 3)
                status, diff = compare_value(paper_val, result_val)
                total_checks += 1
                if status == "EXACT":
                    exact_matches += 1
                elif status == "OK (rounding)":
                    rounding_matches += 1
                else:
                    mismatch_count += 1
                    mismatches.append(f"Per-var {variable} {method} h={h}: paper={paper_val}, result={result_val}")
                lines.append(f"| {variable} | {method} | h={h} | {paper_val:.3f} | {result_val:.3f} | {status} | {diff:.4f} |")

    # --- 5. Ablation table ---
    lines.append("\n## 5. Ablation (tab:ablation)\n")
    lines.append("Ablation values are computed from `results/ablation_results.json`.\n")

    ablation_path = RESULTS_DIR / "ablation_results.json"
    if ablation_path.exists():
        with open(ablation_path) as f:
            ablation_data = json.load(f)

        lines.append("| Step | Era | Paper | Result | Status | Diff |")
        lines.append("|------|-----|-------|--------|--------|------|")

        for step_name, paper_vals in PAPER_ABLATION.items():
            for era, paper_val in paper_vals.items():
                # Try to find matching step in ablation data
                found = False
                for step in ablation_data.get("steps", []):
                    if step.get("label", "").startswith(step_name[:10]):
                        key = "val_mase" if era == "validation" else "test_mase"
                        if key in step:
                            result_val = round(step[key], 3)
                            status, diff = compare_value(paper_val, result_val)
                            total_checks += 1
                            if status == "EXACT":
                                exact_matches += 1
                            elif status == "OK (rounding)":
                                rounding_matches += 1
                            else:
                                mismatch_count += 1
                                mismatches.append(f"Ablation {step_name} {era}: paper={paper_val}, result={result_val}")
                            lines.append(f"| {step_name} | {era} | {paper_val:.3f} | {result_val:.3f} | {status} | {diff:.4f} |")
                            found = True
                            break
                if not found:
                    lines.append(f"| {step_name} | {era} | {paper_val:.3f} | N/A | SKIPPED (no match in ablation data) | --- |")
    else:
        lines.append("Ablation results file not found. Skipping.\n")

    # --- Summary ---
    lines.append("\n## Summary\n")
    lines.append(f"- **Total checks:** {total_checks}")
    lines.append(f"- **Exact matches:** {exact_matches}")
    lines.append(f"- **Rounding matches (diff <= 0.0015):** {rounding_matches}")
    lines.append(f"- **Mismatches:** {mismatch_count}")

    if mismatches:
        lines.append("\n### All Mismatches\n")
        for m in mismatches:
            lines.append(f"- {m}")
    else:
        lines.append("\nNo mismatches found. All paper values match result files.")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    report = run_audit()
    REPORT_PATH.write_text(report)
    print(f"Report written to {REPORT_PATH}")
    print()
    # Print summary to stdout
    for line in report.split("\n"):
        if line.startswith("- **") or line.startswith("### ") or (line.startswith("- ") and "MISMATCH" not in line and "paper=" in line):
            print(line)
        elif "MISMATCH" in line:
            print(line)
