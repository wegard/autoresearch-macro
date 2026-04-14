"""Generate live (most-recent-origin) forecasts for the MacroLab dashboard.

For each country, this script:
  1. Loads the best informed Chronos-2 search config from results/<country>/
  2. Re-fits Chronos-2 with that config on the latest available data and
     emits quantile forecasts (q10/q25/q50/q75/q90) for horizons 1..12.
  3. Runs BVAR and ETS baselines at the same forecast origin (point only)
     so the dashboard can show comparison lines next to the fan chart.

Outputs land in results/live/<country>.json, ready for
scripts/build_live_forecasts_json.py to assemble into a single artifact JSON.

Usage:
    uv run python src/live_forecast.py                     # all three countries
    uv run python src/live_forecast.py --country norway    # one country
    uv run python src/live_forecast.py --origin 2026-04-01 # override origin
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from baselines import BVARBaseline, ETSBaseline, load_country_panel
from prepare import ForecastOrigin, MacroPanel
from train import (
    TRANSFORM_FUNCTIONS,
    build_ag_dataset,
)

try:
    from calibration import (
        CALIBRATOR_PATH,
        apply_calibrator,
        load_calibrator,
    )
except ImportError:  # calibration layer optional at import time
    CALIBRATOR_PATH = None
    apply_calibrator = None
    load_calibrator = None

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
LIVE_DIR = RESULTS_DIR / "live"

COUNTRIES = ("norway", "canada", "sweden")

# Which search-state file holds the best informed config for each country.
# Mirrors webapp/_data/prepare_results.py.
SEARCH_STATE_FILES: dict[str, str] = {
    "norway": "search_state_llm_42.json",
    "canada": "search_state_llm_42.json",
    "sweden": "search_state_llm_fixedgate_42.json",
}

# Quantile levels emitted for the fan chart.
QUANTILE_LEVELS: list[float] = [0.1, 0.25, 0.5, 0.75, 0.9]

# Maximum forecast horizon (months). Matches train.PREDICTION_LENGTH so the
# fan chart shows a smooth band rather than four scattered horizons.
PREDICTION_LENGTH: int = 12

# How many historical months to embed alongside each target series.
HISTORY_MONTHS: int = 60


# ---------------------------------------------------------------------------
# Display metadata for targets
# ---------------------------------------------------------------------------

# (display_name, unit) per target. Mirrors variable_catalog.csv but only for
# the four targets the search optimizes over.
TARGET_DISPLAY: dict[str, dict[str, str]] = {
    "cpi": {
        "display_name": "Consumer prices (CPI)",
        "unit": "12-month % change",
    },
    "industrial_production": {
        "display_name": "Industrial production",
        "unit": "Index (SA)",
    },
    "retail_sales": {
        "display_name": "Retail sales",
        "unit": "Index (SA)",
    },
    "unemployment": {
        "display_name": "Unemployment rate",
        "unit": "%",
    },
}

COUNTRY_DISPLAY: dict[str, str] = {
    "norway": "Norway",
    "canada": "Canada",
    "sweden": "Sweden",
}


# ---------------------------------------------------------------------------
# Best-config loading
# ---------------------------------------------------------------------------


@dataclass
class BestConfig:
    """The best informed Chronos-2 config for a country."""

    country: str
    label: str
    val_mase: float
    config: dict[str, Any]
    source_file: str


def load_best_config(country: str) -> BestConfig:
    """Load the best informed Chronos-2 config from the search state JSON."""
    filename = SEARCH_STATE_FILES[country]
    path = RESULTS_DIR / country / filename
    if not path.exists():
        raise FileNotFoundError(
            f"No search state for {country} at {path}. "
            "Run an LLM search first or update SEARCH_STATE_FILES."
        )
    payload = json.loads(path.read_text())
    return BestConfig(
        country=country,
        label="LLM informed search (best config)",
        val_mase=float(payload["best_score"]),
        config=payload["best_config"],
        source_file=str(path.relative_to(PROJECT_ROOT)),
    )


# ---------------------------------------------------------------------------
# Forecast origin selection
# ---------------------------------------------------------------------------


def _today_utc() -> date:
    return datetime.now(UTC).date()


def make_live_origin(panel: MacroPanel, origin_date: date) -> ForecastOrigin:
    """Build a ForecastOrigin for `origin_date` using publication-lag-aware data.

    Unlike build_validation_origins, we do not supply actuals — there are
    none, since these horizons are in the future. The `actuals` dict is
    therefore empty.
    """
    available = panel.available_at(origin_date)
    return ForecastOrigin(
        origin_date=origin_date,
        available_data=available,
        actuals={},
    )


# ---------------------------------------------------------------------------
# Chronos-2 quantile inference
# ---------------------------------------------------------------------------


def _make_predictor_with_quantiles(
    initial_data: pd.DataFrame,
    targets: list[str],
    covariates: list[str],
    *,
    fine_tune: bool,
    fine_tune_steps: int,
    fine_tune_lr: float,
    model_path: str = "amazon/chronos-2",
) -> Any:
    """Fit a TimeSeriesPredictor configured to emit our quantile levels.

    train.fit_predictor() doesn't accept quantile_levels, so we mirror its
    body with the extra constructor argument. Otherwise the configuration is
    identical so the fit matches the search-time evaluation.
    """
    from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

    ag_data = build_ag_dataset(initial_data, targets, covariates, context_length=None)
    if ag_data.empty:
        raise RuntimeError("AutoGluon dataset is empty; check publication lags / data.")

    ts_data = TimeSeriesDataFrame.from_data_frame(
        ag_data, id_column="item_id", timestamp_column="timestamp",
    )

    hyperparameters: dict[str, Any] = {"Chronos-2": {"model_path": model_path}}
    if fine_tune:
        hyperparameters["Chronos-2"]["fine_tune"] = True
        hyperparameters["Chronos-2"]["fine_tune_steps"] = fine_tune_steps
        hyperparameters["Chronos-2"]["fine_tune_lr"] = fine_tune_lr

    predictor = TimeSeriesPredictor(
        prediction_length=PREDICTION_LENGTH,
        eval_metric="MASE",
        freq="ME",
        verbosity=0,
        quantile_levels=QUANTILE_LEVELS,
    )
    predictor.fit(ts_data, hyperparameters=hyperparameters, time_limit=1800)
    return predictor


def chronos2_quantile_forecast(
    panel: MacroPanel,
    origin: ForecastOrigin,
    best_config: BestConfig,
    calibrator: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Re-fit Chronos-2 with the best informed config and emit quantile forecasts.

    If `calibrator` is supplied, the raw quantile outputs are passed
    through `calibration.apply_calibrator` per (country, target,
    horizon) before serialisation, so the dashboard shows bands whose
    empirical coverage matches their label. Calibrator is fit once on
    the validation era (src/calibration.py fit) and reused across
    publishes.

    Returns {target: {"last_data_date": "YYYY-MM-DD", "horizons": [
        {"horizon": 1, "date": "YYYY-MM-DD", "q10": ..., "q25": ..., ...},
        ...
    ]}}.
    """
    from autogluon.timeseries import TimeSeriesDataFrame

    cfg = best_config.config
    raw_covs: list[str] = list(cfg.get("covariates", []))
    transforms: dict[str, str] = dict(cfg.get("transforms", {}))
    context_length: int | None = cfg.get("context_length")

    # Apply the best-config transforms to the train module so build_ag_dataset
    # picks them up. (train uses module-level globals.)
    import train as _train

    _train.TRANSFORMS = {
        k: v for k, v in transforms.items() if v in TRANSFORM_FUNCTIONS
    }

    targets = panel.targets()
    available_covs = [c for c in raw_covs if c in origin.available_data.columns]

    logger.info(
        "Chronos-2 live forecast: targets=%s, covariates=%s, fine_tune=%s",
        targets, available_covs, cfg.get("fine_tune", False),
    )

    predictor = _make_predictor_with_quantiles(
        origin.available_data, targets, available_covs,
        fine_tune=bool(cfg.get("fine_tune", False)),
        fine_tune_steps=int(cfg.get("fine_tune_steps", 1000)),
        fine_tune_lr=float(cfg.get("fine_tune_lr", 1e-5)),
    )

    # Build inference dataset from the same available data. We rebuild rather
    # than reuse the fit dataset because the fit dataset is internally consumed
    # by AutoGluon and not exposed.
    ag_data = build_ag_dataset(
        origin.available_data, targets, available_covs, context_length,
    )
    ts_data = TimeSeriesDataFrame.from_data_frame(
        ag_data, id_column="item_id", timestamp_column="timestamp",
    )
    predictions = predictor.predict(ts_data)
    # Reset transforms to default to avoid leaking state across calls.
    _train.TRANSFORMS = {}

    # AutoGluon prediction frame: MultiIndex (item_id, timestamp), columns
    # ["mean", "0.1", "0.25", "0.5", "0.75", "0.9"].
    quantile_cols = [str(q) for q in QUANTILE_LEVELS]
    out: dict[str, dict[str, Any]] = {}

    for target in targets:
        if target not in predictions.index.get_level_values("item_id"):
            continue
        target_preds = predictions.loc[target]  # DataFrame indexed by timestamp
        target_series = origin.available_data[target].dropna()
        if target_series.empty:
            continue
        last_data_date = target_series.index[-1].date().isoformat()

        horizons: list[dict[str, Any]] = []
        for h_idx in range(len(target_preds)):
            row = target_preds.iloc[h_idx]
            ts = target_preds.index[h_idx]
            h = h_idx + 1
            entry: dict[str, Any] = {
                "horizon": h,
                "date": pd.Timestamp(ts).date().isoformat(),
                "mean": float(row["mean"]),
            }
            raw_quantiles: dict[float, float] = {}
            for q, col in zip(QUANTILE_LEVELS, quantile_cols, strict=True):
                if col in row:
                    raw_quantiles[q] = float(row[col])
            # Apply calibrator if available. Falls back to identity for
            # (country, target, horizon) triples the calibrator hasn't
            # been fit on.
            if calibrator is not None and apply_calibrator is not None and raw_quantiles:
                cal_quantiles = apply_calibrator(
                    raw_quantiles, best_config.country, target, h, calibrator,
                )
            else:
                cal_quantiles = raw_quantiles
            for q, value in cal_quantiles.items():
                entry[f"q{int(round(q * 100))}"] = float(value)
            horizons.append(entry)

        out[target] = {
            "last_data_date": last_data_date,
            "horizons": horizons,
        }

    return out


# ---------------------------------------------------------------------------
# Baseline point forecasts at the live origin
# ---------------------------------------------------------------------------


def baseline_point_forecast(
    method: Any,
    origin: ForecastOrigin,
    targets: list[str],
    horizons: list[int],
) -> dict[str, dict[str, Any]]:
    """Run a baseline at the live origin and capture point forecasts."""
    out: dict[str, dict[str, Any]] = {}
    for target in targets:
        preds = method.forecast_origin(origin, target, horizons)
        if not preds:
            continue
        target_series = origin.available_data[target].dropna()
        if target_series.empty:
            continue
        last_data_date = target_series.index[-1].date()
        # Forecast date for horizon h is last_data_date + h months (month-end).
        forecast_horizons: list[dict[str, Any]] = []
        for h in horizons:
            if h not in preds:
                continue
            fc_date = (
                pd.Timestamp(last_data_date) + pd.DateOffset(months=h)
            ) + pd.offsets.MonthEnd(0)
            forecast_horizons.append({
                "horizon": h,
                "date": fc_date.date().isoformat(),
                "mean": float(preds[h]),
            })
        if forecast_horizons:
            out[target] = {
                "last_data_date": last_data_date.isoformat(),
                "horizons": forecast_horizons,
            }
    return out


# ---------------------------------------------------------------------------
# History extraction
# ---------------------------------------------------------------------------


def extract_history(
    available: pd.DataFrame, target: str, n_months: int = HISTORY_MONTHS,
) -> list[dict[str, Any]]:
    """Return the last n_months of `target` as [{date, value}, ...]."""
    series = available[target].dropna() if target in available.columns else pd.Series(dtype=float)
    if series.empty:
        return []
    series = series.iloc[-n_months:]
    return [
        {"date": ts.date().isoformat(), "value": float(v)}
        for ts, v in series.items()
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_country(
    country: str,
    origin_date: date,
    calibrator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the full live-forecast pipeline for one country."""
    logger.info("=== Live forecast: %s, origin=%s ===", country, origin_date)
    panel = load_country_panel(country)
    origin = make_live_origin(panel, origin_date)

    targets = panel.targets()
    horizons = list(range(1, PREDICTION_LENGTH + 1))

    # Best informed Chronos-2 with quantiles (optionally recalibrated).
    best = load_best_config(country)
    t0 = time.time()
    chronos2 = chronos2_quantile_forecast(panel, origin, best, calibrator=calibrator)
    chronos2_runtime = time.time() - t0
    logger.info(
        "Chronos-2 done in %.1fs (calibrator: %s)",
        chronos2_runtime, "on" if calibrator is not None else "off",
    )

    # BVAR (best multivariate baseline).
    t0 = time.time()
    bvar = baseline_point_forecast(
        BVARBaseline(country=country), origin, targets, horizons,
    )
    bvar_runtime = time.time() - t0
    logger.info("BVAR done in %.1fs", bvar_runtime)

    # ETS (univariate baseline).
    t0 = time.time()
    ets = baseline_point_forecast(
        ETSBaseline(), origin, targets, horizons,
    )
    ets_runtime = time.time() - t0
    logger.info("ETS done in %.1fs", ets_runtime)

    # Build per-target payload.
    target_payload: dict[str, Any] = {}
    for target in targets:
        history = extract_history(origin.available_data, target)
        meta = TARGET_DISPLAY.get(target, {"display_name": target, "unit": ""})
        target_payload[target] = {
            "display_name": meta["display_name"],
            "unit": meta["unit"],
            "history": history,
            "models": {
                "chronos2_informed": chronos2.get(target),
                "bvar": bvar.get(target),
                "ets": ets.get(target),
            },
        }

    return {
        "country": country,
        "display_name": COUNTRY_DISPLAY.get(country, country.title()),
        "forecast_origin": origin_date.isoformat(),
        "data_vintage": panel.data.index.max().date().isoformat()
        if not panel.data.empty else None,
        "best_config": {
            "label": best.label,
            "val_mase": best.val_mase,
            "config": best.config,
            "source_file": best.source_file,
        },
        "models_runtime_seconds": {
            "chronos2_informed": round(chronos2_runtime, 1),
            "bvar": round(bvar_runtime, 1),
            "ets": round(ets_runtime, 1),
        },
        "targets": target_payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--country", choices=COUNTRIES, default=None,
        help="Run only one country (default: all)",
    )
    parser.add_argument(
        "--origin", type=str, default=None,
        help="Forecast origin date (YYYY-MM-DD). Default: today (UTC).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=LIVE_DIR,
        help="Where to write per-country JSON files.",
    )
    parser.add_argument(
        "--no-calibration", action="store_true",
        help="Skip quantile recalibration even if a calibrator file is "
             "present. Useful for publishing raw Chronos-2 quantiles "
             "(e.g., for debugging or for zero-shot comparisons).",
    )
    parser.add_argument(
        "--calibrator", type=Path, default=None,
        help="Override path to calibrator JSON. Defaults to "
             "results/calibration/calibrator.json.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    origin_date = (
        date.fromisoformat(args.origin) if args.origin else _today_utc()
    )
    targets_to_run = [args.country] if args.country else list(COUNTRIES)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load calibrator once (small file, ~tens of KB). Default path
    # applies when not explicitly overridden and calibration is not
    # disabled. If the file is missing we quietly fall through to
    # identity calibration — a developer is probably bootstrapping.
    calibrator: dict[str, Any] | None = None
    if not args.no_calibration and load_calibrator is not None:
        cal_path = args.calibrator or CALIBRATOR_PATH
        if cal_path is not None and cal_path.exists():
            calibrator = load_calibrator(cal_path)
            logger.info("Loaded calibrator from %s", cal_path)
        else:
            logger.warning(
                "No calibrator at %s; publishing raw Chronos-2 quantiles. "
                "Run `uv run python src/calibration.py fit` after a "
                "validation-era backtest to enable calibration.",
                cal_path,
            )

    for country in targets_to_run:
        try:
            payload = run_country(country, origin_date, calibrator=calibrator)
        except Exception:
            logger.exception("Live forecast failed for %s", country)
            continue
        out_path = args.output_dir / f"{country}.json"
        out_path.write_text(json.dumps(payload, indent=2, default=str))
        logger.info("Wrote %s", out_path)


if __name__ == "__main__":
    main()
