"""Generate rolling forecasts for the webapp visualization.

Runs Chronos-2 with the best search config on origins spanning
the full available range (2006 through present), and exports
forecasts + actuals as JSON for the webapp.

Requires GPU and ML dependencies. Run separately from prepare_results.py.

Usage:
    uv run python webapp/_data/generate_forecasts.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from prepare import (
    HORIZONS,
    MacroPanel,
    _build_origins,
    load_panel,
)
from train import (
    apply_config_overrides,
    fit_predictor,
    forecast_origin,
)

logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent / "rolling_forecasts.json"
SEARCH_STATE_PATH = PROJECT_ROOT / "results" / "search_state.json"


def load_best_config() -> dict | None:
    """Load the best config from the search state."""
    if not SEARCH_STATE_PATH.exists():
        logger.warning("No search state found at %s", SEARCH_STATE_PATH)
        return None
    state = json.loads(SEARCH_STATE_PATH.read_text())
    return state.get("best_config")


def generate_rolling_forecasts(
    panel: MacroPanel,
    config: dict,
    start: str = "2006-01",
    end: str | None = None,
    step_months: int = 1,
) -> list[dict]:
    """Generate forecasts for all origins in the given range.

    Returns a list of dicts, one per variable × origin × horizon.
    """
    horizons = list(HORIZONS)

    # Determine end date: latest panel date minus max horizon
    if end is None:
        last = panel.data.index[-1]
        end_dt = last - pd.DateOffset(months=max(horizons))
        end = end_dt.strftime("%Y-%m")

    # Build origins for the full range
    origins = _build_origins(panel, start, end, step_months, horizons)
    logger.info("Built %d origins from %s to %s", len(origins), start, end)

    targets = panel.targets()

    # Apply config overrides
    import train
    for key, value in config.items():
        upper_key = key.upper()
        if hasattr(train, upper_key):
            setattr(train, upper_key, value)

    covariates = [c for c in train.COVARIATES if c in panel.data.columns]

    # Fit predictor once
    logger.info("Fitting predictor (model=%s, covariates=%s)...", train.MODEL_PATH, covariates)
    predictor = fit_predictor(
        origins[0].available_data, targets, covariates,
        prediction_length=train.PREDICTION_LENGTH,
        model_path=train.MODEL_PATH,
        fine_tune=train.FINE_TUNE,
        fine_tune_steps=train.FINE_TUNE_STEPS,
        learning_rate=train.FINE_TUNE_LR,
    )
    logger.info("Predictor ready.")

    # Generate forecasts
    records: list[dict] = []
    start_time = time.time()

    for i, origin in enumerate(origins):
        if (i + 1) % 20 == 0 or i == 0:
            elapsed = time.time() - start_time
            logger.info("  Origin %d/%d (%.1fs)", i + 1, len(origins), elapsed)

        preds = forecast_origin(
            origin, targets, horizons,
            predictor, covariates, train.CONTEXT_LENGTH,
        )

        origin_date = origin.origin_date
        origin_ts = pd.Timestamp(origin_date)

        for var in targets:
            var_preds = preds.get(var, {})
            var_actuals = origin.actuals.get(var, pd.Series(dtype=float))

            for h in horizons:
                target_date = origin_ts + pd.DateOffset(months=h) + pd.offsets.MonthEnd(0)

                record = {
                    "variable": var,
                    "origin": str(origin_date),
                    "h": h,
                    "target_date": target_date.strftime("%Y-%m-%d"),
                    "forecast": round(float(var_preds[h]), 4) if h in var_preds else None,
                    "actual": round(float(var_actuals[h]), 4) if h in var_actuals.index else None,
                }
                records.append(record)

    elapsed = time.time() - start_time
    logger.info("Generated %d forecast records in %.1fs", len(records), elapsed)
    return records


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load best config
    config = load_best_config()
    if config is None:
        logger.info("No search state found, using default config (zero-shot)")
        config = {}

    logger.info("Best config: %s", json.dumps(config, default=str))

    # Load panel
    panel = load_panel()
    logger.info("Panel loaded: %d variables, %d months", len(panel.data.columns), len(panel.data))

    # Generate forecasts
    records = generate_rolling_forecasts(panel, config)

    # Save
    OUTPUT_PATH.write_text(json.dumps(records))
    logger.info("Saved %d records to %s", len(records), OUTPUT_PATH)

    # Also export the historical actuals for the chart background
    actuals_path = OUTPUT_PATH.parent / "actuals_timeseries.json"
    targets = panel.targets()
    actuals = []
    for date, row in panel.data.iterrows():
        for var in targets:
            val = row.get(var)
            if pd.notna(val):
                actuals.append({
                    "variable": var,
                    "date": date.strftime("%Y-%m-%d"),
                    "value": round(float(val), 4),
                })
    actuals_path.write_text(json.dumps(actuals))
    logger.info("Saved %d actuals records to %s", len(actuals), actuals_path)


if __name__ == "__main__":
    main()
