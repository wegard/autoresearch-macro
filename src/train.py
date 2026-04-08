"""Agent sandbox for the autoresearch-macro project.

This file is EDITABLE by the search agent. It loads Chronos-2 via
AutoGluon TimeSeriesPredictor, applies covariate selection and
transformations from the config section, and produces forecasts.

The search agent modifies the CONFIGURATION SECTION below.
Everything below the config section should generally stay stable.

Usage:
    python src/train.py                        # Run on validation era
    python src/train.py --era test             # Run on test era (frozen)
    python src/train.py --save                 # Save results
    python src/train.py --origins 10           # Subsample origins for speed
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ===================================================================
# CONFIGURATION SECTION — the search agent edits this
# ===================================================================

# Model
MODEL_PATH = "amazon/chronos-2"  # 120M params, native covariate support
PREDICTION_LENGTH = 12  # max forecast horizon (months)

# Covariates to include (from panel.covariates())
COVARIATES: list[str] = []  # empty = univariate (no covariates)

# Transformations: variable_name → transform_name
# Available: "none", "log_diff", "pct_change_12", "pct_change_1",
#            "standardize_60", "ma_3", "ma_6"
TRANSFORMS: dict[str, str] = {}

# Context length (lookback window in months)
CONTEXT_LENGTH: int | None = None  # None = use all available data

# Fine-tuning (LoRA by default for Chronos-2)
FINE_TUNE = False
FINE_TUNE_STEPS = 1000
FINE_TUNE_LR = 1e-5

# Grouping: "univariate" (separate model per target) or
#           "all_targets" (single model for all targets)
GROUPING = "univariate"

# Number of samples for probabilistic forecast (median used as point forecast)
NUM_SAMPLES = 20

# ===================================================================
# END CONFIGURATION SECTION
# ===================================================================


# ---------------------------------------------------------------------------
# Imports from project (after config so agent sees config first)
# ---------------------------------------------------------------------------

from evaluate import ForecastResult, evaluate, format_results_table, save_result  # noqa: E402
from prepare import (  # noqa: E402
    HORIZONS,
    ForecastOrigin,
    MacroPanel,
    build_test_origins,
    build_validation_origins,
    load_panel,
    log_diff,
    ma,
    pct_change,
    standardize,
)


# ---------------------------------------------------------------------------
# Transformation pipeline
# ---------------------------------------------------------------------------

TRANSFORM_FUNCTIONS: dict[str, Any] = {
    "none": lambda s: s,
    "log_diff": log_diff,
    "pct_change_12": lambda s: pct_change(s, periods=12),
    "pct_change_1": lambda s: pct_change(s, periods=1),
    "standardize_60": lambda s: standardize(s, window=60),
    "ma_3": lambda s: ma(s, window=3),
    "ma_6": lambda s: ma(s, window=6),
}


def apply_transforms(data: pd.DataFrame, targets: list[str]) -> pd.DataFrame:
    """Apply configured transformations to covariate columns only.

    Target variables are NEVER transformed because the evaluation protocol
    compares forecasts against original-scale actuals. Transforming targets
    would produce forecasts in a different scale (e.g., standardized) that
    cannot be compared to the raw actuals.

    Returns a new DataFrame with transformed covariate columns.
    """
    result = data.copy()
    for col, transform_name in TRANSFORMS.items():
        if col in targets:
            logger.warning(
                "Ignoring transform '%s' on target '%s' — target transforms "
                "would produce forecasts in wrong scale for evaluation.",
                transform_name, col,
            )
            continue
        if col in result.columns and transform_name in TRANSFORM_FUNCTIONS:
            result[col] = TRANSFORM_FUNCTIONS[transform_name](result[col])
    return result


# ---------------------------------------------------------------------------
# Dataset builder
# ---------------------------------------------------------------------------


def build_ag_dataset(
    available_data: pd.DataFrame,
    targets: list[str],
    covariates: list[str],
    context_length: int | None = None,
) -> pd.DataFrame:
    """Convert available panel data into AutoGluon-compatible long format.

    AutoGluon TimeSeriesDataFrame expects:
        item_id | timestamp | target | [covariate columns...]

    Each target variable becomes a separate item_id. Covariates are
    included as additional columns (past covariates).

    Args:
        available_data: Panel data available at the forecast origin.
        targets: Target variable names to forecast.
        covariates: Covariate variable names to include.
        context_length: If set, truncate to last N observations.

    Returns:
        DataFrame in long format ready for TimeSeriesDataFrame conversion.
    """
    # Apply transformations (covariates only — targets stay in original scale)
    transformed = apply_transforms(available_data, targets)

    # Truncate to context length
    if context_length is not None and len(transformed) > context_length:
        transformed = transformed.iloc[-context_length:]

    # Drop rows where all values are NaN (after transforms like log_diff)
    transformed = transformed.dropna(how="all")

    rows = []
    for target_var in targets:
        if target_var not in transformed.columns:
            continue
        target_series = transformed[target_var].dropna()
        if target_series.empty:
            continue

        # Keep only the contiguous tail of valid observations.
        # Transforms like log_diff create leading NaN (from diff) and
        # scattered NaN (from log of negative values). Dropping them
        # can create gaps that break AutoGluon's frequency inference.
        # Instead, find the last contiguous block of valid monthly data.
        valid_idx = target_series.index
        if len(valid_idx) > 1:
            expected = pd.date_range(start=valid_idx[0], end=valid_idx[-1], freq="ME")
            if not valid_idx.equals(expected):
                # Find longest contiguous suffix
                contiguous_start = len(valid_idx) - 1
                for i in range(len(valid_idx) - 2, -1, -1):
                    gap = (valid_idx[i + 1] - valid_idx[i]).days
                    if gap > 35:  # more than one month
                        break
                    contiguous_start = i
                target_series = target_series.iloc[contiguous_start:]
                valid_idx = target_series.index

        for ts in valid_idx:
            row: dict[str, Any] = {
                "item_id": target_var,
                "timestamp": ts,
                "target": float(target_series.loc[ts]),
            }
            # Add covariates
            for cov in covariates:
                if cov in transformed.columns:
                    val = transformed.loc[ts, cov]
                    row[cov] = float(val) if pd.notna(val) else np.nan
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def get_current_config() -> dict[str, Any]:
    """Capture the current configuration for reproducibility."""
    return {
        "model_path": MODEL_PATH,
        "prediction_length": PREDICTION_LENGTH,
        "covariates": COVARIATES,
        "transforms": TRANSFORMS,
        "context_length": CONTEXT_LENGTH,
        "fine_tune": FINE_TUNE,
        "fine_tune_steps": FINE_TUNE_STEPS,
        "fine_tune_lr": FINE_TUNE_LR,
        "grouping": GROUPING,
        "num_samples": NUM_SAMPLES,
    }


# ---------------------------------------------------------------------------
# Model setup and forecasting
# ---------------------------------------------------------------------------


def fit_predictor(
    initial_data: pd.DataFrame,
    targets: list[str],
    covariates: list[str],
    prediction_length: int = PREDICTION_LENGTH,
    model_path: str = MODEL_PATH,
    fine_tune: bool = FINE_TUNE,
    fine_tune_steps: int = FINE_TUNE_STEPS,
    learning_rate: float = FINE_TUNE_LR,
) -> Any:
    """Create, fit, and return an AutoGluon TimeSeriesPredictor with Chronos-2.

    For zero-shot mode, fit() loads the model weights (no training).
    The fitted predictor can then be used to predict() on any data.

    Returns:
        Fitted TimeSeriesPredictor.
    """
    try:
        from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
    except ImportError:
        raise ImportError(
            "AutoGluon TimeSeries not installed. Run: uv sync --extra ml"
        )

    # Build initial dataset for fitting
    ag_data = build_ag_dataset(initial_data, targets, covariates, context_length=None)
    ts_data = TimeSeriesDataFrame.from_data_frame(
        ag_data, id_column="item_id", timestamp_column="timestamp",
    )

    hyperparameters: dict[str, Any] = {
        "Chronos-2": {"model_path": model_path}
    }
    if fine_tune:
        hyperparameters["Chronos-2"]["fine_tune"] = True
        hyperparameters["Chronos-2"]["fine_tune_steps"] = fine_tune_steps
        hyperparameters["Chronos-2"]["fine_tune_lr"] = learning_rate

    time_limit = 1800 if fine_tune else 120
    predictor = TimeSeriesPredictor(
        prediction_length=prediction_length,
        eval_metric="MASE",
        freq="ME",
        verbosity=0,
    )
    predictor.fit(ts_data, hyperparameters=hyperparameters, time_limit=time_limit)

    return predictor


def forecast_origin(
    origin: ForecastOrigin,
    targets: list[str],
    horizons: list[int],
    predictor: Any,
    covariates: list[str],
    context_length: int | None,
) -> dict[str, dict[int, float]]:
    """Produce forecasts for a single origin using a fitted predictor.

    Args:
        origin: Forecast origin with available data.
        targets: Target variables to forecast.
        horizons: Forecast horizons (months ahead).
        predictor: Fitted AutoGluon TimeSeriesPredictor.
        covariates: Covariate names to include.
        context_length: Lookback window.

    Returns:
        {variable: {horizon: point_forecast}}.
    """
    from autogluon.timeseries import TimeSeriesDataFrame

    available_covs = [c for c in covariates if c in origin.available_data.columns]
    ag_data = build_ag_dataset(
        origin.available_data, targets, available_covs, context_length
    )

    if ag_data.empty:
        return {}

    try:
        ts_data = TimeSeriesDataFrame.from_data_frame(
            ag_data, id_column="item_id", timestamp_column="timestamp",
        )
    except Exception as e:
        logger.warning("Failed to create TimeSeriesDataFrame at origin %s: %s",
                       origin.origin_date, e)
        return {}

    try:
        predictions = predictor.predict(ts_data)
    except Exception as e:
        logger.warning("Prediction failed at origin %s: %s", origin.origin_date, e)
        return {}

    # Extract point forecasts (mean) for each target and horizon
    result: dict[str, dict[int, float]] = {}
    for target_var in targets:
        if target_var not in predictions.index.get_level_values("item_id"):
            continue
        target_preds = predictions.loc[target_var]
        result[target_var] = {}
        for h in horizons:
            if h <= len(target_preds):
                val = target_preds.iloc[h - 1]["mean"]
                result[target_var][h] = float(val)

    return result


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run(
    panel: MacroPanel,
    era: str = "validation",
    horizons: list[int] | None = None,
    max_origins: int | None = None,
    retune_interval: int | None = None,
) -> ForecastResult:
    """Run the full forecasting pipeline.

    Args:
        panel: MacroPanel with all data.
        era: 'validation' or 'test'.
        horizons: Forecast horizons (default: HORIZONS).
        max_origins: If set, subsample to this many origins.
        retune_interval: If set, re-fit the predictor every N origins.
            None = fit once (default). 12 = re-tune annually.

    Returns:
        ForecastResult ready for evaluation.
    """
    if horizons is None:
        horizons = list(HORIZONS)

    # Build origins
    if era == "test":
        origins = build_test_origins(panel, horizons=horizons)
    else:
        origins = build_validation_origins(panel, horizons=horizons)

    # Subsample origins for speed
    if max_origins is not None and len(origins) > max_origins:
        rng = np.random.default_rng(42)
        indices = sorted(rng.choice(len(origins), size=max_origins, replace=False))
        origins = [origins[i] for i in indices]
        logger.info("Subsampled to %d origins", len(origins))

    targets = panel.targets()
    available_covs = [c for c in COVARIATES if c in panel.data.columns]

    start = time.time()

    retune_desc = f", retune every {retune_interval}" if retune_interval else ""
    logger.info(
        "Running Chronos-2 (%s): %d targets, %d origins, covariates=%s, fine_tune=%s%s",
        MODEL_PATH, len(targets), len(origins), available_covs, FINE_TUNE, retune_desc,
    )

    # Fit predictor on first origin's data
    logger.info("Fitting predictor (loading model, fine_tune=%s)...", FINE_TUNE)
    predictor = fit_predictor(
        origins[0].available_data, targets, available_covs,
        prediction_length=PREDICTION_LENGTH,
        model_path=MODEL_PATH,
        fine_tune=FINE_TUNE,
        fine_tune_steps=FINE_TUNE_STEPS,
        learning_rate=FINE_TUNE_LR,
    )
    logger.info("Predictor ready (%.1fs)", time.time() - start)

    point_forecasts: dict[str, pd.DataFrame] = {}

    for i, origin in enumerate(origins):
        # Periodic re-tuning: re-fit the predictor every N origins
        if retune_interval and i > 0 and i % retune_interval == 0:
            logger.info("  Re-tuning predictor at origin %d/%d...", i + 1, len(origins))
            predictor = fit_predictor(
                origin.available_data, targets, available_covs,
                prediction_length=PREDICTION_LENGTH,
                model_path=MODEL_PATH,
                fine_tune=FINE_TUNE,
                fine_tune_steps=FINE_TUNE_STEPS,
                learning_rate=FINE_TUNE_LR,
            )

        if (i + 1) % 10 == 0 or i == 0:
            elapsed = time.time() - start
            logger.info("  Origin %d/%d (%.1fs elapsed)", i + 1, len(origins), elapsed)

        preds = forecast_origin(
            origin, targets, horizons,
            predictor, available_covs, CONTEXT_LENGTH,
        )

        for var, horizon_preds in preds.items():
            if var not in point_forecasts:
                point_forecasts[var] = {}
            point_forecasts[var][origin.origin_date] = horizon_preds

    # Convert accumulated dicts to DataFrames
    for var in list(point_forecasts.keys()):
        point_forecasts[var] = pd.DataFrame.from_dict(
            point_forecasts[var], orient="index"
        )

    runtime = time.time() - start
    logger.info("Chronos-2 complete: %.1fs, %d variables with forecasts",
                runtime, len(point_forecasts))

    method_name = f"chronos2_{'ft' if FINE_TUNE else 'zs'}"

    return ForecastResult(
        method_name=method_name,
        point_forecasts=point_forecasts,
        config=get_current_config(),
        runtime_seconds=runtime,
        era=era,
        horizons=horizons,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def apply_config_overrides(config_path: str) -> None:
    """Load a JSON config file and override module-level config variables.

    This allows search.py to set configs programmatically without
    editing train.py source code.
    """
    overrides = json.loads(Path(config_path).read_text())

    # Modify globals of the actual running module (handles both
    # __main__ and import-as-train cases).
    import sys
    this_module = sys.modules[__name__]

    config_vars = {
        "model_path", "prediction_length", "covariates", "transforms",
        "context_length", "fine_tune", "fine_tune_steps", "fine_tune_lr",
        "grouping", "num_samples",
    }
    for key, value in overrides.items():
        upper_key = key.upper()
        if key.lower() in config_vars:
            setattr(this_module, upper_key, value)
            logger.info("Config override: %s = %s", upper_key, value)
        else:
            logger.warning("Unknown config key ignored: %s", key)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chronos-2 forecasting pipeline (agent sandbox)",
    )
    parser.add_argument(
        "--era", type=str, default="validation", choices=["validation", "test"],
        help="Evaluation era (default: validation)",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results to results/ directory",
    )
    parser.add_argument(
        "--origins", type=int, default=None,
        help="Subsample to N origins for speed",
    )
    parser.add_argument(
        "--config-file", type=str, default=None,
        help="JSON file with config overrides (used by search.py)",
    )
    parser.add_argument(
        "--retune-interval", type=int, default=None,
        help="Re-fit predictor every N origins (None = fit once)",
    )
    parser.add_argument(
        "--country", type=str, default="norway",
        choices=["norway", "canada", "sweden"],
        help="Country to run for (default: norway)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.config_file:
        apply_config_overrides(args.config_file)

    if args.country == "norway":
        panel = load_panel()
    else:
        from baselines import load_country_panel
        panel = load_country_panel(args.country)

    fr = run(panel, era=args.era, max_origins=args.origins, retune_interval=args.retune_interval)
    fr.country = args.country
    eval_result = evaluate(fr, panel)
    print(format_results_table(eval_result))

    if args.save:
        save_result(fr, eval_result)


if __name__ == "__main__":
    main()
