"""Empirical coverage backtest for Chronos-2's predictive quantile bands.

For each country, fits the best informed config on data through the first
test-era origin, rolls through all subsequent test-era origins emitting
quantile forecasts (q10/q25/q50/q75/q90) at each, and computes the
fraction of realised actuals that fell within each nominal coverage band.

Purpose: the live dashboard's fan charts use Chronos-2's native quantile
output, which was not explicitly calibrated against the paper's evaluation
eras. This script gives an honest, ex-post answer to "does the 80% band
actually contain 80% of the realisations?".

Outputs (under results/coverage/):
  <country>.parquet       Per-origin raw quantiles + actuals
  coverage_summary.csv    Hit-rate table (country, target, horizon, band,
                          nominal, empirical, n)
  coverage_summary.json   Same, machine-readable

Usage:
  uv run python src/coverage_backtest.py                    # all countries
  uv run python src/coverage_backtest.py --country norway
  uv run python src/coverage_backtest.py --max-origins 20   # smoke test
  uv run python src/coverage_backtest.py --zero-shot        # override
                                                            # fine_tune=False
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

from baselines import load_country_panel
from live_forecast import (
    PREDICTION_LENGTH,
    QUANTILE_LEVELS,
    _make_predictor_with_quantiles,
    load_best_config,
)
from prepare import build_test_origins
from train import TRANSFORM_FUNCTIONS, build_ag_dataset

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
COVERAGE_DIR = RESULTS_DIR / "coverage"
COVERAGE_ZS_DIR = RESULTS_DIR / "coverage_zs"

COUNTRIES = ("norway", "canada", "sweden")

# Nominal coverage pairs reported by the summary:
#   (lower_quantile, upper_quantile, nominal_coverage_fraction)
COVERAGE_BANDS: list[tuple[float, float, float]] = [
    (0.1, 0.9, 0.80),
    (0.25, 0.75, 0.50),
]


def _apply_config_transforms(cfg: dict[str, Any]) -> None:
    """Mutate train.TRANSFORMS to match the best-config transforms.

    train.build_ag_dataset reads TRANSFORMS from train's module globals
    at call time; we follow the same pattern as live_forecast.
    """
    import train as _train

    _train.TRANSFORMS = {
        k: v for k, v in cfg.get("transforms", {}).items() if v in TRANSFORM_FUNCTIONS
    }


def _reset_config_transforms() -> None:
    import train as _train

    _train.TRANSFORMS = {}


def run_backtest_country(
    country: str,
    max_origins: int | None = None,
    zero_shot: bool = False,
) -> pd.DataFrame:
    """Produce per-origin quantile forecasts across the test era.

    Returns a DataFrame with one row per (origin, target, horizon) and
    columns [country, target, origin, horizon, actual, q10, q25, q50,
    q75, q90, mean].

    When `zero_shot=True`, overrides the best-config's fine-tune flag
    and runs Chronos-2 without LoRA adaptation. Used to isolate the
    effect of fine-tuning on predictive-quantile calibration.
    """
    from autogluon.timeseries import TimeSeriesDataFrame

    panel = load_country_panel(country)
    best = load_best_config(country)
    cfg = best.config

    _apply_config_transforms(cfg)

    targets = panel.targets()
    covs = [c for c in cfg.get("covariates", []) if c in panel.data.columns]
    horizons = list(range(1, PREDICTION_LENGTH + 1))
    context_length = cfg.get("context_length")

    origins = build_test_origins(panel, horizons=horizons)
    if max_origins is not None and len(origins) > max_origins:
        origins = origins[:max_origins]
        logger.info("Truncated to first %d origins for smoke test", max_origins)

    fine_tune = bool(cfg.get("fine_tune", False)) and not zero_shot
    mode_label = "zero-shot" if zero_shot else ("fine-tuned" if fine_tune else "zero-shot (config)")

    logger.info(
        "=== Coverage backtest: %s (%s) — %d origins, targets=%s, covariates=%s ===",
        country, mode_label, len(origins), targets, covs,
    )

    t0 = time.time()
    predictor = _make_predictor_with_quantiles(
        origins[0].available_data, targets, covs,
        fine_tune=fine_tune,
        fine_tune_steps=int(cfg.get("fine_tune_steps", 1000)),
        fine_tune_lr=float(cfg.get("fine_tune_lr", 1e-5)),
    )
    logger.info("Predictor fit done in %.1fs", time.time() - t0)

    quantile_cols = [str(q) for q in QUANTILE_LEVELS]
    rows: list[dict[str, Any]] = []

    for i, origin in enumerate(origins):
        if (i + 1) % 20 == 0 or i == 0:
            logger.info("  origin %d/%d (%s)", i + 1, len(origins), origin.origin_date)

        ag_data = build_ag_dataset(origin.available_data, targets, covs, context_length)
        if ag_data.empty:
            continue

        try:
            ts_data = TimeSeriesDataFrame.from_data_frame(
                ag_data, id_column="item_id", timestamp_column="timestamp",
            )
            predictions = predictor.predict(ts_data)
        except Exception as e:
            logger.warning("Predict failed at origin %s: %s", origin.origin_date, e)
            continue

        for target in targets:
            if target not in predictions.index.get_level_values("item_id"):
                continue
            if target not in origin.actuals:
                continue
            target_preds = predictions.loc[target]
            actuals_series = origin.actuals[target]

            for h_idx in range(len(target_preds)):
                h = h_idx + 1
                if h not in actuals_series.index:
                    continue
                actual = actuals_series[h]
                if pd.isna(actual):
                    continue
                row = target_preds.iloc[h_idx]
                entry: dict[str, Any] = {
                    "country": country,
                    "target": target,
                    "origin": origin.origin_date,
                    "horizon": h,
                    "actual": float(actual),
                    "mean": float(row["mean"]),
                }
                for q, col in zip(QUANTILE_LEVELS, quantile_cols, strict=True):
                    if col in row:
                        entry[f"q{int(round(q * 100))}"] = float(row[col])
                rows.append(entry)

    _reset_config_transforms()
    return pd.DataFrame(rows)


def compute_coverage_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-origin rows into empirical coverage per band."""
    results: list[dict[str, Any]] = []
    if df.empty:
        return pd.DataFrame(results)

    for (country, target, horizon), group in df.groupby(["country", "target", "horizon"]):
        for lo, hi, nominal in COVERAGE_BANDS:
            lo_col = f"q{int(round(lo * 100))}"
            hi_col = f"q{int(round(hi * 100))}"
            if lo_col not in group.columns or hi_col not in group.columns:
                continue
            within = (group["actual"] >= group[lo_col]) & (group["actual"] <= group[hi_col])
            n = int(within.count())
            hits = int(within.sum())
            results.append({
                "country": country,
                "target": target,
                "horizon": int(horizon),
                "band": f"{int(lo * 100)}-{int(hi * 100)}%",
                "nominal_coverage": nominal,
                "empirical_coverage": round(hits / n, 4) if n > 0 else None,
                "n_observations": n,
            })
    return pd.DataFrame(results).sort_values(
        ["country", "target", "horizon", "nominal_coverage"]
    ).reset_index(drop=True)


def write_outputs(
    per_country: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for country, df in per_country.items():
        df.to_parquet(output_dir / f"{country}.parquet")
        logger.info("Wrote %s (%d rows)", output_dir / f"{country}.parquet", len(df))

    combined = pd.concat(per_country.values(), ignore_index=True) if per_country else pd.DataFrame()
    summary = compute_coverage_summary(combined)

    csv_path = output_dir / "coverage_summary.csv"
    summary.to_csv(csv_path, index=False)
    json_path = output_dir / "coverage_summary.json"
    json_path.write_text(json.dumps(summary.to_dict(orient="records"), indent=2, default=str))
    logger.info("Wrote %s and %s", csv_path, json_path)

    if not summary.empty:
        # Aggregate headline across all (country, target, horizon) for a
        # quick top-line readability check.
        overall = summary.groupby(["band", "nominal_coverage"]).agg(
            empirical_coverage=("empirical_coverage", "mean"),
            n=("n_observations", "sum"),
        ).reset_index()
        print()
        print("Overall empirical coverage (pooled across country × target × horizon):")
        print(overall.to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", choices=COUNTRIES, default=None)
    parser.add_argument(
        "--max-origins", type=int, default=None,
        help="Truncate to first N origins (smoke test).",
    )
    parser.add_argument(
        "--zero-shot", action="store_true",
        help="Force fine_tune=False even if the best config enables LoRA. "
             "Used to isolate the effect of fine-tuning on calibration.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Override output directory. Defaults to results/coverage (or "
             "results/coverage_zs when --zero-shot is set).",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = COVERAGE_ZS_DIR if args.zero_shot else COVERAGE_DIR

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    countries = [args.country] if args.country else list(COUNTRIES)
    per_country: dict[str, pd.DataFrame] = {}

    for c in countries:
        try:
            df = run_backtest_country(
                c, max_origins=args.max_origins, zero_shot=args.zero_shot,
            )
            per_country[c] = df
        except Exception:
            logger.exception("Coverage backtest failed for %s", c)

    if not per_country:
        return 1

    write_outputs(per_country, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
