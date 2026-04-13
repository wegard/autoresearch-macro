"""Frozen evaluation harness for the autoresearch-macro project.

Computes metrics for point and probabilistic forecasts, stores results,
and produces comparison tables. This file is LOCKED — the search agent
cannot modify it.

Usage:
    python src/evaluate.py --results-dir results/validation/baseline_rw
    python src/evaluate.py --compare results/validation/baseline_rw results/validation/baseline_ar
    python src/evaluate.py --summary results/validation/baseline_rw
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prepare import (
    HORIZONS,
    TARGET_VARIABLES,
    MacroPanel,
    build_test_origins,
    build_validation_origins,
    evaluate_forecasts,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"

# Subperiod definitions for test era reporting
TEST_SUBPERIODS: dict[str, tuple[str, str]] = {
    "full_test": ("2016-01", "2025-12"),
    "pre_covid": ("2016-01", "2019-12"),
    "covid": ("2020-01", "2021-12"),
    "post_covid": ("2022-01", "2025-12"),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ForecastResult:
    """Complete forecast output from any method.

    Attributes:
        method_name: Identifier for the forecasting method.
        point_forecasts: {variable: DataFrame(index=origin_dates, columns=horizons)}.
        quantile_forecasts: {variable: {tau: DataFrame}} or None.
        config: Full configuration for reproducibility.
        runtime_seconds: Total wall-clock time for producing all forecasts.
        timestamp: When the forecasts were generated.
        era: 'validation' or 'test'.
        horizons: Forecast horizons evaluated.
    """

    method_name: str
    point_forecasts: dict[str, pd.DataFrame]
    quantile_forecasts: dict[str, dict[float, pd.DataFrame]] | None = None
    config: dict[str, Any] = field(default_factory=dict)
    runtime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    era: str = "validation"
    horizons: list[int] = field(default_factory=lambda: list(HORIZONS))
    country: str = "norway"


@dataclass
class EvaluationResult:
    """Structured evaluation metrics for a forecast result.

    Attributes:
        method_name: Identifier for the forecasting method.
        era: 'validation' or 'test'.
        metrics: {variable: {horizon: {metric_name: value}}}.
        subperiod_metrics: {subperiod: {variable: {horizon: {metric: value}}}}.
        summary: Aggregated metrics across variables.
    """

    method_name: str
    era: str
    metrics: dict[str, dict[int, dict[str, float]]]
    subperiod_metrics: dict[str, dict[str, dict[int, dict[str, float]]]]
    summary: dict[int, dict[str, float]]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    forecast_result: ForecastResult,
    panel: MacroPanel,
) -> EvaluationResult:
    """Evaluate a ForecastResult against the panel.

    Builds origins for the appropriate era, computes all metrics,
    and returns a structured EvaluationResult.
    """
    if forecast_result.era == "test":
        origins = build_test_origins(
            panel, horizons=forecast_result.horizons
        )
    else:
        origins = build_validation_origins(
            panel, horizons=forecast_result.horizons
        )

    # Full-period metrics
    metrics = evaluate_forecasts(
        forecast_result.point_forecasts,
        origins,
        forecast_result.horizons,
    )

    # Subperiod metrics (test era only)
    subperiod_metrics: dict[str, dict[str, dict[int, dict[str, float]]]] = {}
    if forecast_result.era == "test":
        for sp_name, (sp_start, sp_end) in TEST_SUBPERIODS.items():
            sp_origins = [
                o for o in origins
                if pd.Timestamp(sp_start).date() <= o.origin_date
                <= (pd.Timestamp(sp_end) + pd.offsets.MonthEnd(0)).date()
            ]
            if sp_origins:
                subperiod_metrics[sp_name] = evaluate_forecasts(
                    forecast_result.point_forecasts,
                    sp_origins,
                    forecast_result.horizons,
                )

    # Summary: average across target variables
    summary = _compute_summary(metrics, forecast_result.horizons)

    return EvaluationResult(
        method_name=forecast_result.method_name,
        era=forecast_result.era,
        metrics=metrics,
        subperiod_metrics=subperiod_metrics,
        summary=summary,
    )


def _compute_summary(
    metrics: dict[str, dict[int, dict[str, float]]],
    horizons: list[int],
) -> dict[int, dict[str, float]]:
    """Average metrics across all target variables for each horizon."""
    summary: dict[int, dict[str, float]] = {}
    for h in horizons:
        rmse_vals, mae_vals, mase_vals = [], [], []
        for var in TARGET_VARIABLES:
            if var in metrics and h in metrics[var]:
                m = metrics[var][h]
                rmse_vals.append(m.get("rmse", float("nan")))
                mae_vals.append(m.get("mae", float("nan")))
                mase_vals.append(m.get("mase", float("nan")))
        if rmse_vals:
            summary[h] = {
                "avg_rmse": float(np.nanmean(rmse_vals)),
                "avg_mae": float(np.nanmean(mae_vals)),
                "avg_mase": float(np.nanmean(mase_vals)),
                "n_variables": len(rmse_vals),
            }
    return summary


# ---------------------------------------------------------------------------
# Results I/O
# ---------------------------------------------------------------------------


def save_result(
    forecast_result: ForecastResult,
    eval_result: EvaluationResult,
    base_dir: Path | None = None,
) -> Path:
    """Save forecast and evaluation results to disk.

    Directory structure:
        results/{country}/{era}/{method_name}/   (when country != "norway")
        results/{era}/{method_name}/             (backward compat for Norway)
            config.json
            metrics.json
            point_forecasts.parquet   (one column per variable-horizon)
            summary.txt
    """
    if base_dir is None:
        base_dir = RESULTS_DIR
    country = getattr(forecast_result, "country", "norway")
    if country and country != "norway":
        out_dir = base_dir / country / forecast_result.era / forecast_result.method_name
    else:
        out_dir = base_dir / forecast_result.era / forecast_result.method_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Config
    config_out = {
        "method_name": forecast_result.method_name,
        "era": forecast_result.era,
        "country": country,
        "horizons": forecast_result.horizons,
        "runtime_seconds": forecast_result.runtime_seconds,
        "timestamp": forecast_result.timestamp.isoformat(),
        "config": forecast_result.config,
    }
    (out_dir / "config.json").write_text(json.dumps(config_out, indent=2, default=str))

    # Metrics
    metrics_out = {
        "metrics": _serialize_metrics(eval_result.metrics),
        "subperiod_metrics": {
            sp: _serialize_metrics(m) for sp, m in eval_result.subperiod_metrics.items()
        },
        "summary": {str(h): v for h, v in eval_result.summary.items()},
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics_out, indent=2))

    # Point forecasts as parquet
    frames = []
    for var, df in forecast_result.point_forecasts.items():
        for h in df.columns:
            col_name = f"{var}_h{h}"
            frames.append(df[[h]].rename(columns={h: col_name}))
    if frames:
        combined = pd.concat(frames, axis=1)
        combined.to_parquet(out_dir / "point_forecasts.parquet")

    # Human-readable summary
    summary_text = format_results_table(eval_result)
    (out_dir / "summary.txt").write_text(summary_text)

    logger.info("Results saved to %s", out_dir)
    return out_dir


def _serialize_metrics(
    metrics: dict[str, dict[int, dict[str, float]]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Convert int horizon keys to strings for JSON serialization."""
    return {
        var: {str(h): m for h, m in horizons.items()}
        for var, horizons in metrics.items()
    }


def load_eval_result(results_dir: Path) -> EvaluationResult:
    """Load an EvaluationResult from a saved directory."""
    metrics_raw = json.loads((results_dir / "metrics.json").read_text())
    config_raw = json.loads((results_dir / "config.json").read_text())

    metrics = {
        var: {int(h): m for h, m in horizons.items()}
        for var, horizons in metrics_raw["metrics"].items()
    }
    subperiod_metrics = {
        sp: {var: {int(h): m for h, m in horizons.items()} for var, horizons in sp_m.items()}
        for sp, sp_m in metrics_raw.get("subperiod_metrics", {}).items()
    }
    summary = {int(h): v for h, v in metrics_raw.get("summary", {}).items()}

    return EvaluationResult(
        method_name=config_raw["method_name"],
        era=config_raw["era"],
        metrics=metrics,
        subperiod_metrics=subperiod_metrics,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Comparison and reporting
# ---------------------------------------------------------------------------


def format_results_table(eval_result: EvaluationResult) -> str:
    """Format evaluation results as a readable text table."""
    lines = [
        f"{'=' * 80}",
        f"Evaluation: {eval_result.method_name}  (era: {eval_result.era})",
        f"{'=' * 80}",
        "",
    ]

    # Per-variable results
    for var in sorted(eval_result.metrics.keys()):
        lines.append(f"  {var}:")
        lines.append(f"    {'Horizon':>8s}  {'RMSE':>10s}  {'MAE':>10s}  {'MASE':>10s}  {'N':>6s}")
        for h in sorted(eval_result.metrics[var].keys()):
            m = eval_result.metrics[var][h]
            lines.append(
                f"    {h:>8d}  {m.get('rmse', float('nan')):>10.4f}  "
                f"{m.get('mae', float('nan')):>10.4f}  "
                f"{m.get('mase', float('nan')):>10.4f}  "
                f"{m.get('n_origins', 0):>6d}"
            )
        lines.append("")

    # Summary
    if eval_result.summary:
        lines.append("  Summary (average across targets):")
        lines.append(f"    {'Horizon':>8s}  {'Avg RMSE':>10s}  {'Avg MAE':>10s}  {'Avg MASE':>10s}")
        for h in sorted(eval_result.summary.keys()):
            s = eval_result.summary[h]
            lines.append(
                f"    {h:>8d}  {s.get('avg_rmse', float('nan')):>10.4f}  "
                f"{s.get('avg_mae', float('nan')):>10.4f}  "
                f"{s.get('avg_mase', float('nan')):>10.4f}"
            )
        lines.append("")

    return "\n".join(lines)


def compare_methods(
    eval_results: list[EvaluationResult],
    metric: str = "rmse",
) -> str:
    """Compare multiple methods side by side.

    Returns a formatted comparison table showing the chosen metric
    for each method, variable, and horizon.
    """
    if not eval_results:
        return "No results to compare."

    methods = [r.method_name for r in eval_results]
    all_vars = sorted(
        set().union(*(r.metrics.keys() for r in eval_results))
    )
    all_horizons = sorted({
        h for r in eval_results for var_h in r.metrics.values() for h in var_h.keys()
    })

    lines = [
        f"{'=' * 80}",
        f"Comparison — metric: {metric}",
        f"{'=' * 80}",
    ]

    # Header
    header = f"  {'Variable':>25s}  {'h':>3s}"
    for m in methods:
        header += f"  {m:>15s}"
    lines.append(header)
    lines.append(f"  {'-' * (len(header) - 2)}")

    for var in all_vars:
        for h in all_horizons:
            row = f"  {var:>25s}  {h:>3d}"
            for r in eval_results:
                val = r.metrics.get(var, {}).get(h, {}).get(metric, float("nan"))
                row += f"  {val:>15.4f}"
            lines.append(row)
        lines.append("")

    # Summary row
    lines.append(f"  {'AVERAGE':>25s}")
    for h in all_horizons:
        row = f"  {'':>25s}  {h:>3d}"
        for r in eval_results:
            key = f"avg_{metric}"
            val = r.summary.get(h, {}).get(key, float("nan"))
            row += f"  {val:>15.4f}"
        lines.append(row)

    return "\n".join(lines)


def relative_metrics(
    result: EvaluationResult,
    baseline: EvaluationResult,
    metric: str = "rmse",
) -> dict[str, dict[int, float]]:
    """Compute metric ratios relative to a baseline.

    Returns {variable: {horizon: ratio}}, where ratio < 1 means
    the result method is better than the baseline.
    """
    ratios: dict[str, dict[int, float]] = {}
    for var in result.metrics:
        if var not in baseline.metrics:
            continue
        ratios[var] = {}
        for h in result.metrics[var]:
            if h not in baseline.metrics.get(var, {}):
                continue
            r_val = result.metrics[var][h].get(metric, float("nan"))
            b_val = baseline.metrics[var][h].get(metric, float("nan"))
            if b_val != 0 and not np.isnan(b_val):
                ratios[var][h] = r_val / b_val
    return ratios


# ---------------------------------------------------------------------------
# Diebold-Mariano test
# ---------------------------------------------------------------------------


def diebold_mariano(
    forecasts_1: dict[str, pd.DataFrame],
    forecasts_2: dict[str, pd.DataFrame],
    origins: list[ForecastOrigin],
    horizon: int,
    variable: str,
    loss: str = "squared",
) -> dict[str, float]:
    """Diebold-Mariano test for equal predictive ability.

    Tests H0: E[d_t] = 0 where d_t = L(e1_t) - L(e2_t).
    Negative DM statistic means method 1 is better.

    Uses Newey-West HAC standard errors to account for serial
    correlation in multi-step forecast errors.

    Args:
        forecasts_1: Point forecasts from method 1.
        forecasts_2: Point forecasts from method 2.
        origins: List of ForecastOrigin objects with actuals.
        horizon: Forecast horizon to test.
        variable: Target variable name.
        loss: "squared" (MSE) or "absolute" (MAE).

    Returns:
        {"dm_stat": float, "p_value": float, "n": int}
    """
    from scipy import stats

    # Collect loss differentials
    d_list: list[float] = []
    for origin in origins:
        od = origin.origin_date
        if variable not in origin.actuals:
            continue
        if horizon not in origin.actuals[variable].index:
            continue

        actual = origin.actuals[variable][horizon]

        # Get forecasts at this origin
        fc1 = forecasts_1.get(variable)
        fc2 = forecasts_2.get(variable)
        if fc1 is None or fc2 is None:
            continue
        if od not in fc1.index or od not in fc2.index:
            continue
        if horizon not in fc1.columns or horizon not in fc2.columns:
            continue

        f1 = fc1.loc[od, horizon]
        f2 = fc2.loc[od, horizon]

        if pd.isna(actual) or pd.isna(f1) or pd.isna(f2):
            continue

        e1 = actual - f1
        e2 = actual - f2

        if loss == "squared":
            d_list.append(e1**2 - e2**2)
        else:
            d_list.append(abs(e1) - abs(e2))

    if len(d_list) < 10:
        return {"dm_stat": float("nan"), "p_value": float("nan"), "n": len(d_list)}

    d = np.array(d_list)
    n = len(d)
    d_mean = np.mean(d)

    # Newey-West HAC variance estimator
    # Bandwidth = h - 1 (for h-step-ahead forecasts)
    bandwidth = max(1, horizon - 1)
    gamma_0 = np.mean((d - d_mean) ** 2)
    gamma_sum = gamma_0
    for k in range(1, bandwidth + 1):
        weight = 1 - k / (bandwidth + 1)  # Bartlett kernel
        gamma_k = np.mean((d[k:] - d_mean) * (d[:-k] - d_mean))
        gamma_sum += 2 * weight * gamma_k

    if gamma_sum <= 0:
        return {"dm_stat": float("nan"), "p_value": float("nan"), "n": n}

    dm_stat = d_mean / np.sqrt(gamma_sum / n)
    p_value = 2 * (1 - stats.norm.cdf(abs(dm_stat)))

    return {"dm_stat": float(dm_stat), "p_value": float(p_value), "n": n}


def dm_test_table(
    results_dir: Path,
    era: str,
    panel: MacroPanel,
    reference_method: str = "random_walk",
) -> pd.DataFrame:
    """Run DM tests for all methods against a reference.

    Returns a DataFrame with columns: variable, horizon, method, dm_stat, p_value.
    """
    from prepare import build_test_origins, build_validation_origins

    if era == "test":
        origins = build_test_origins(panel)
    else:
        origins = build_validation_origins(panel)

    era_dir = results_dir / era
    methods = sorted([d.name for d in era_dir.iterdir() if d.is_dir() and d.name != reference_method])

    # Load reference forecasts
    ref_parquet = era_dir / reference_method / "point_forecasts.parquet"
    if not ref_parquet.exists():
        return pd.DataFrame()
    ref_fc = _load_point_forecasts(ref_parquet)

    rows = []
    for method_name in methods:
        method_parquet = era_dir / method_name / "point_forecasts.parquet"
        if not method_parquet.exists():
            continue
        method_fc = _load_point_forecasts(method_parquet)

        for var in panel.targets():
            for h in HORIZONS:
                result = diebold_mariano(
                    ref_fc, method_fc, origins, h, var, loss="squared"
                )
                rows.append({
                    "variable": var,
                    "horizon": h,
                    "method": method_name,
                    "reference": reference_method,
                    "dm_stat": result["dm_stat"],
                    "p_value": result["p_value"],
                    "n": result["n"],
                })

    return pd.DataFrame(rows)


def _load_point_forecasts(parquet_path: Path) -> dict[str, pd.DataFrame]:
    """Load point forecasts from parquet into {variable: DataFrame} format."""
    df = pd.read_parquet(parquet_path)
    forecasts: dict[str, pd.DataFrame] = {}
    for col in df.columns:
        # Columns are like "cpi_h1", "cpi_h3", etc.
        parts = col.rsplit("_h", 1)
        if len(parts) != 2:
            continue
        var, h_str = parts
        h = int(h_str)
        if var not in forecasts:
            forecasts[var] = pd.DataFrame(index=df.index)
        forecasts[var][h] = df[col]
    return forecasts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluation harness for autoresearch-macro",
    )
    parser.add_argument(
        "--summary", type=str, metavar="DIR",
        help="Show summary of results in DIR",
    )
    parser.add_argument(
        "--compare", nargs="+", metavar="DIR",
        help="Compare results from multiple directories",
    )
    parser.add_argument(
        "--metric", type=str, default="rmse",
        choices=["rmse", "mae", "mase"],
        help="Metric to use for comparison (default: rmse)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.summary:
        result = load_eval_result(Path(args.summary))
        print(format_results_table(result))
        return

    if args.compare:
        results = [load_eval_result(Path(d)) for d in args.compare]
        print(compare_methods(results, metric=args.metric))
        return

    print("Use --summary or --compare. See --help for usage.")


if __name__ == "__main__":
    main()
