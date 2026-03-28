"""Tests for baseline forecasting methods (baselines.py)."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from baselines import (
    ARIMABaseline,
    AutoregressiveAR,
    ETSBaseline,
    RandomWalk,
    SeasonalNaive,
    run_baseline,
)
from prepare import ForecastOrigin, MacroPanel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_panel(
    variables: list[str] | None = None,
    start: str = "1995-01",
    periods: int = 360,
) -> MacroPanel:
    if variables is None:
        variables = ["cpi", "industrial_production", "retail_sales", "unemployment",
                      "brent_crude"]
    idx = pd.date_range(start=start, periods=periods, freq="ME")
    rng = np.random.default_rng(42)
    data = pd.DataFrame(
        {v: 100 + rng.standard_normal(periods).cumsum() for v in variables},
        index=idx,
    )
    return MacroPanel(
        data=data,
        metadata={v: {"description": v} for v in variables},
        publication_lags={v: 10 for v in variables},
        first_available={v: idx[0] for v in variables},
        last_updated=datetime.now(),
    )


def _make_origin(
    panel: MacroPanel,
    origin_date: date,
    horizons: list[int] | None = None,
) -> ForecastOrigin:
    if horizons is None:
        horizons = [1, 3, 6, 12]
    available = panel.available_at(origin_date)
    origin_ts = pd.Timestamp(origin_date)

    actuals: dict[str, pd.Series] = {}
    for var in panel.targets():
        if var not in panel.data.columns:
            continue
        horizon_vals: dict[int, float] = {}
        for h in horizons:
            target_date = origin_ts + pd.DateOffset(months=h)
            target_date = target_date + pd.offsets.MonthEnd(0)
            if target_date in panel.data.index:
                val = panel.data.loc[target_date, var]
                if pd.notna(val):
                    horizon_vals[h] = float(val)
        if horizon_vals:
            actuals[var] = pd.Series(horizon_vals, dtype=float)

    return ForecastOrigin(
        origin_date=origin_date,
        available_data=available,
        actuals=actuals,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRandomWalk:
    def test_returns_last_value(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        rw = RandomWalk()
        preds = rw.forecast_origin(origin, "cpi", [1, 3, 6, 12])

        # All horizons should return the same value (last observed)
        assert len(preds) == 4
        vals = list(preds.values())
        assert all(v == vals[0] for v in vals)

    def test_constant_series_zero_error(self):
        """Random walk on a constant series should produce zero error."""
        panel = _make_panel()
        # Replace cpi with constant
        panel.data["cpi"] = 100.0
        origin = _make_origin(panel, date(2010, 6, 15))
        rw = RandomWalk()
        preds = rw.forecast_origin(origin, "cpi", [1, 3])

        for h, pred in preds.items():
            actual = origin.actuals["cpi"].get(h)
            if actual is not None:
                assert abs(pred - actual) < 1e-10

    def test_empty_data_returns_empty(self):
        panel = _make_panel(variables=["cpi", "brent_crude"])
        origin = _make_origin(panel, date(2010, 6, 15))
        rw = RandomWalk()
        preds = rw.forecast_origin(origin, "nonexistent", [1])
        assert preds == {}


class TestSeasonalNaive:
    def test_returns_seasonal_values(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        sn = SeasonalNaive()
        preds = sn.forecast_origin(origin, "cpi", [1, 12])
        assert len(preds) > 0

    def test_short_series_returns_empty(self):
        """Seasonal naive needs at least 13 months of data."""
        panel = _make_panel(start="2010-01", periods=10)
        origin = _make_origin(panel, date(2010, 9, 15))
        sn = SeasonalNaive()
        preds = sn.forecast_origin(origin, "cpi", [1])
        assert preds == {}


class TestAutoregressive:
    def test_linear_trend(self):
        """AR should handle a linear trend reasonably."""
        panel = _make_panel()
        # Replace cpi with a linear trend
        n = len(panel.data)
        panel.data["cpi"] = np.arange(n, dtype=float) * 0.1 + 100
        origin = _make_origin(panel, date(2010, 6, 15))

        ar = AutoregressiveAR(max_lag=4)
        preds = ar.forecast_origin(origin, "cpi", [1, 3])
        assert len(preds) > 0

    def test_returns_predictions_for_all_horizons(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        ar = AutoregressiveAR(max_lag=6)
        preds = ar.forecast_origin(origin, "cpi", [1, 3, 6, 12])
        assert len(preds) == 4


class TestARIMA:
    def test_returns_predictions(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        arima = ARIMABaseline()
        preds = arima.forecast_origin(origin, "cpi", [1, 3, 6, 12])
        assert len(preds) == 4

    def test_short_series_returns_empty(self):
        panel = _make_panel(start="2010-01", periods=20)
        origin = _make_origin(panel, date(2011, 6, 15))
        arima = ARIMABaseline()
        preds = arima.forecast_origin(origin, "cpi", [1])
        assert preds == {}

    def test_order_cache_works(self):
        panel = _make_panel()
        arima = ARIMABaseline()
        origin1 = _make_origin(panel, date(2010, 6, 15))
        arima.forecast_origin(origin1, "cpi", [1])
        assert "cpi" in arima._order_cache

        origin2 = _make_origin(panel, date(2010, 7, 15))
        preds = arima.forecast_origin(origin2, "cpi", [1, 3])
        assert len(preds) >= 1


class TestETS:
    def test_returns_predictions(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        ets = ETSBaseline()
        preds = ets.forecast_origin(origin, "cpi", [1, 3, 6, 12])
        assert len(preds) == 4

    def test_short_series_returns_empty(self):
        panel = _make_panel(start="2010-01", periods=20)
        origin = _make_origin(panel, date(2011, 6, 15))
        ets = ETSBaseline()
        preds = ets.forecast_origin(origin, "cpi", [1])
        assert preds == {}

    def test_constant_series(self):
        """ETS on a constant series should forecast the constant."""
        panel = _make_panel()
        panel.data["cpi"] = 100.0
        origin = _make_origin(panel, date(2010, 6, 15))
        ets = ETSBaseline()
        preds = ets.forecast_origin(origin, "cpi", [1, 3])
        for h, pred in preds.items():
            assert abs(pred - 100.0) < 1.0  # close to constant


class TestRunBaseline:
    def test_run_random_walk(self):
        panel = _make_panel()
        fr = run_baseline(RandomWalk(), panel, era="validation", horizons=[1, 3])

        assert fr.method_name == "random_walk"
        assert fr.era == "validation"
        assert len(fr.point_forecasts) > 0

        for var, df in fr.point_forecasts.items():
            assert 1 in df.columns
            assert 3 in df.columns
            assert len(df) > 0

    def test_run_ar(self):
        panel = _make_panel()
        fr = run_baseline(AutoregressiveAR(), panel, era="validation", horizons=[1])

        assert fr.method_name == "ar"
        assert len(fr.point_forecasts) > 0
