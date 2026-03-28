"""Baseline forecasting methods for the autoresearch-macro project.

Implements naive and classical univariate baselines that serve as
reference points for evaluating foundation model performance.

Usage:
    python src/baselines.py --method random_walk --era validation
    python src/baselines.py --method ar --era validation
    python src/baselines.py --all --era validation
"""

from __future__ import annotations

import argparse
import logging
import time
import warnings
from typing import Protocol

import numpy as np
import pandas as pd

from evaluate import (
    ForecastResult,
    evaluate,
    format_results_table,
    save_result,
)
from prepare import (
    HORIZONS,
    ForecastOrigin,
    MacroPanel,
    build_test_origins,
    build_validation_origins,
    load_panel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Baseline protocol
# ---------------------------------------------------------------------------


class BaselineMethod(Protocol):
    """Interface that all baseline methods must implement."""

    name: str

    def forecast_origin(
        self,
        origin: ForecastOrigin,
        target: str,
        horizons: list[int],
    ) -> dict[int, float]:
        """Produce point forecasts for a single origin and target.

        Args:
            origin: Forecast origin with available data.
            target: Variable name to forecast.
            horizons: List of forecast horizons (months ahead).

        Returns:
            {horizon: point_forecast}.
        """
        ...


# ---------------------------------------------------------------------------
# Naive baselines
# ---------------------------------------------------------------------------


class RandomWalk:
    """Random walk (no-change) forecast.

    Forecast = last observed value for the target variable.
    This is the simplest possible baseline.
    """

    name = "random_walk"

    def forecast_origin(
        self,
        origin: ForecastOrigin,
        target: str,
        horizons: list[int],
    ) -> dict[int, float]:
        if target not in origin.available_data.columns:
            return {}
        series = origin.available_data[target].dropna()
        if series.empty:
            return {}
        last_value = float(series.iloc[-1])
        return {h: last_value for h in horizons}


class SeasonalNaive:
    """Seasonal naive forecast.

    For h-step ahead: use the observation from h months ago
    (same month, previous year for h=12).
    """

    name = "seasonal_naive"

    def forecast_origin(
        self,
        origin: ForecastOrigin,
        target: str,
        horizons: list[int],
    ) -> dict[int, float]:
        if target not in origin.available_data.columns:
            return {}
        series = origin.available_data[target].dropna()
        if len(series) < 13:
            return {}

        result: dict[int, float] = {}
        for h in horizons:
            # Look back 12 months from origin, then go h months forward
            # Equivalent to: value from (12 - h) months before origin
            lookback = 12 - (h % 12)
            if lookback == 0:
                lookback = 12
            if lookback <= len(series):
                result[h] = float(series.iloc[-lookback])
        return result


# ---------------------------------------------------------------------------
# AR baseline
# ---------------------------------------------------------------------------


class AutoregressiveAR:
    """Direct AR(p) forecast with BIC lag selection.

    Fits separate AR models for each horizon using OLS.
    Selects lag order p in [1, max_lag] by minimizing BIC.
    """

    name = "ar"

    def __init__(self, max_lag: int = 12) -> None:
        self.max_lag = max_lag

    def forecast_origin(
        self,
        origin: ForecastOrigin,
        target: str,
        horizons: list[int],
    ) -> dict[int, float]:
        if target not in origin.available_data.columns:
            return {}
        series = origin.available_data[target].dropna()
        if len(series) < self.max_lag + 2:
            return {}

        y = series.values
        result: dict[int, float] = {}

        for h in horizons:
            best_bic = np.inf
            best_pred = float(y[-1])  # fallback

            for p in range(1, min(self.max_lag + 1, len(y) - h)):
                pred = self._fit_predict_ar(y, p, h)
                if pred is not None:
                    bic = self._compute_bic(y, p, h)
                    if bic < best_bic:
                        best_bic = bic
                        best_pred = pred

            result[h] = best_pred
        return result

    def _fit_predict_ar(
        self, y: np.ndarray, p: int, h: int
    ) -> float | None:
        """Fit AR(p) via OLS and predict h-step ahead (direct method)."""
        n = len(y)
        if n < p + h + 1:
            return None

        # Build design matrix for direct h-step forecast
        # y_{t+h} = c + a1*y_t + a2*y_{t-1} + ... + ap*y_{t-p+1} + e
        n_obs = n - p - h + 1
        if n_obs < p + 2:
            return None

        X = np.ones((n_obs, p + 1))  # +1 for intercept
        Y = np.zeros(n_obs)

        for i in range(n_obs):
            t = p - 1 + i
            Y[i] = y[t + h]
            for j in range(p):
                X[i, j + 1] = y[t - j]

        try:
            beta, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
        except np.linalg.LinAlgError:
            return None

        # Predict using latest p values
        x_new = np.ones(p + 1)
        for j in range(p):
            x_new[j + 1] = y[-(j + 1)]
        return float(x_new @ beta)

    def _compute_bic(self, y: np.ndarray, p: int, h: int) -> float:
        """Compute BIC for AR(p) with h-step direct regression."""
        n = len(y)
        n_obs = n - p - h + 1
        if n_obs < p + 2:
            return np.inf

        X = np.ones((n_obs, p + 1))
        Y = np.zeros(n_obs)

        for i in range(n_obs):
            t = p - 1 + i
            Y[i] = y[t + h]
            for j in range(p):
                X[i, j + 1] = y[t - j]

        try:
            beta, _, _, _ = np.linalg.lstsq(X, Y, rcond=None)
        except np.linalg.LinAlgError:
            return np.inf

        residuals = Y - X @ beta
        sigma2 = np.mean(residuals**2)
        if sigma2 <= 0:
            return np.inf

        k = p + 1  # number of parameters
        return float(n_obs * np.log(sigma2) + k * np.log(n_obs))


# ---------------------------------------------------------------------------
# ARIMA baseline
# ---------------------------------------------------------------------------


class ARIMABaseline:
    """Auto-ARIMA baseline with AIC order selection.

    Fits ARIMA(p,d,q) on available data via statsmodels, selecting
    the best order by AIC from a grid search. Produces multi-step
    forecasts from the fitted model.
    """

    name = "arima"

    _ORDER_GRID: list[tuple[int, int, int]] = [
        (p, d, q)
        for p in range(4)
        for d in range(2)
        for q in range(3)
    ]

    def __init__(self) -> None:
        self._order_cache: dict[str, tuple[int, int, int]] = {}

    def forecast_origin(
        self,
        origin: ForecastOrigin,
        target: str,
        horizons: list[int],
    ) -> dict[int, float]:
        if target not in origin.available_data.columns:
            return {}
        series = origin.available_data[target].dropna()
        if len(series) < 30:
            return {}

        y = series.values
        max_h = max(horizons)

        # Try cached order first, then full grid search
        order = self._order_cache.get(target)
        forecasts = self._fit_and_forecast(y, order, max_h) if order else None

        if forecasts is None:
            order, forecasts = self._auto_select(y, max_h)
            if order is not None:
                self._order_cache[target] = order

        if forecasts is None:
            # Fallback: random walk
            return {h: float(y[-1]) for h in horizons}

        return {h: float(forecasts[h - 1]) for h in horizons if h <= len(forecasts)}

    def _fit_and_forecast(
        self,
        y: np.ndarray,
        order: tuple[int, int, int],
        steps: int,
    ) -> np.ndarray | None:
        """Fit ARIMA with given order and return multi-step forecast."""
        from statsmodels.tsa.arima.model import ARIMA

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(y, order=order)
                result = model.fit()
                return result.forecast(steps=steps)
        except Exception:
            return None

    def _auto_select(
        self,
        y: np.ndarray,
        steps: int,
    ) -> tuple[tuple[int, int, int] | None, np.ndarray | None]:
        """Grid search over ARIMA orders, select by AIC."""
        from statsmodels.tsa.arima.model import ARIMA

        best_aic = np.inf
        best_order: tuple[int, int, int] | None = None
        best_result = None

        for order in self._ORDER_GRID:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = ARIMA(y, order=order)
                    result = model.fit()
                    if result.aic < best_aic:
                        best_aic = result.aic
                        best_order = order
                        best_result = result
            except Exception:
                continue

        if best_result is None:
            return None, None

        try:
            forecasts = best_result.forecast(steps=steps)
            return best_order, forecasts
        except Exception:
            return best_order, None


# ---------------------------------------------------------------------------
# ETS baseline
# ---------------------------------------------------------------------------


class ETSBaseline:
    """Exponential Smoothing (ETS) baseline with automatic model selection.

    Tries several ETS configurations and selects the best by AIC.
    Uses statsmodels ExponentialSmoothing.
    """

    name = "ets"

    _CONFIGS: list[dict] = [
        {"trend": None, "seasonal": None},
        {"trend": "add", "seasonal": None},
        {"trend": "add", "damped_trend": True, "seasonal": None},
        {"trend": "add", "seasonal": "add", "seasonal_periods": 12},
        {"trend": "add", "damped_trend": True, "seasonal": "add", "seasonal_periods": 12},
    ]

    def forecast_origin(
        self,
        origin: ForecastOrigin,
        target: str,
        horizons: list[int],
    ) -> dict[int, float]:
        if target not in origin.available_data.columns:
            return {}
        series = origin.available_data[target].dropna()
        # Need at least 2 full seasonal cycles for seasonal models
        if len(series) < 30:
            return {}

        y = series.values
        max_h = max(horizons)

        forecasts = self._auto_select_and_forecast(y, max_h)
        if forecasts is None:
            return {h: float(y[-1]) for h in horizons}

        return {h: float(forecasts[h - 1]) for h in horizons if h <= len(forecasts)}

    def _auto_select_and_forecast(
        self, y: np.ndarray, steps: int
    ) -> np.ndarray | None:
        """Try ETS configurations, select best by AIC, forecast."""
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        best_aic = np.inf
        best_result = None

        for cfg in self._CONFIGS:
            # Seasonal models need enough data
            sp = cfg.get("seasonal_periods", 1)
            if len(y) < 2 * sp + 1:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = ExponentialSmoothing(y, **cfg)
                    result = model.fit(optimized=True)
                    if result.aic < best_aic:
                        best_aic = result.aic
                        best_result = result
            except Exception:
                continue

        if best_result is None:
            return None

        try:
            return best_result.forecast(steps)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

AVAILABLE_METHODS: dict[str, BaselineMethod] = {
    "random_walk": RandomWalk(),
    "seasonal_naive": SeasonalNaive(),
    "ar": AutoregressiveAR(),
    "arima": ARIMABaseline(),
    "ets": ETSBaseline(),
}


def run_baseline(
    method: BaselineMethod,
    panel: MacroPanel,
    era: str = "validation",
    horizons: list[int] | None = None,
) -> ForecastResult:
    """Run a baseline method on all origins and all target variables.

    Returns a ForecastResult ready for evaluation.
    """
    if horizons is None:
        horizons = list(HORIZONS)

    if era == "test":
        origins = build_test_origins(panel, horizons=horizons)
    else:
        origins = build_validation_origins(panel, horizons=horizons)

    targets = panel.targets()
    point_forecasts: dict[str, pd.DataFrame] = {}

    start = time.time()

    for target in targets:
        rows: dict = {}
        for origin in origins:
            preds = method.forecast_origin(origin, target, horizons)
            if preds:
                rows[origin.origin_date] = preds
        if rows:
            point_forecasts[target] = pd.DataFrame.from_dict(rows, orient="index")

    runtime = time.time() - start

    logger.info(
        "Baseline %s: %d targets, %d origins, %.1fs",
        method.name, len(point_forecasts), len(origins), runtime,
    )

    return ForecastResult(
        method_name=method.name,
        point_forecasts=point_forecasts,
        config={"method": method.name, "horizons": horizons},
        runtime_seconds=runtime,
        era=era,
        horizons=horizons,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run baseline forecasts",
    )
    parser.add_argument(
        "--method", type=str, choices=list(AVAILABLE_METHODS.keys()),
        help="Which baseline to run",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all baselines",
    )
    parser.add_argument(
        "--era", type=str, default="validation", choices=["validation", "test"],
        help="Evaluation era (default: validation)",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save results to results/ directory",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    panel = load_panel()

    methods_to_run: list[BaselineMethod] = []
    if args.all:
        methods_to_run = list(AVAILABLE_METHODS.values())
    elif args.method:
        methods_to_run = [AVAILABLE_METHODS[args.method]]
    else:
        parser.print_help()
        return

    for method in methods_to_run:
        logger.info("Running baseline: %s", method.name)
        fr = run_baseline(method, panel, era=args.era)
        eval_result = evaluate(fr, panel)
        print(format_results_table(eval_result))

        if args.save:
            save_result(fr, eval_result)


if __name__ == "__main__":
    main()
