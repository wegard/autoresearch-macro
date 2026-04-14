"""Tests for src/prepare.py.

All tests use synthetic data — no API calls required.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
from prepare import (
    HORIZONS,
    MacroPanel,
    _parse_ssb_time,
    build_test_origins,
    build_validation_origins,
    daily_to_monthly,
    evaluate_forecasts,
    ffill_covariates_only,
    load_publication_lags,
    log_diff,
    ma,
    mae,
    mase,
    pct_change,
    pinball_loss,
    quarterly_to_monthly,
    rmse,
    standardize,
    warn_if_targets_stale,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_monthly_index(start: str = "2000-01", periods: int = 240) -> pd.DatetimeIndex:
    """Create a monthly end-of-month DatetimeIndex (20 years by default)."""
    return pd.date_range(start=start, periods=periods, freq="ME")


def _make_panel(
    n_months: int = 240,
    start: str = "2000-01",
    variables: list[str] | None = None,
    lags: dict[str, int] | None = None,
) -> MacroPanel:
    """Create a synthetic MacroPanel for testing."""
    if variables is None:
        variables = ["cpi", "industrial_production", "retail_sales", "unemployment",
                      "brent_crude", "sp500", "policy_rate"]
    if lags is None:
        lags = {
            "cpi": 10,
            "industrial_production": 40,
            "retail_sales": 30,
            "unemployment": 30,
            "brent_crude": 1,
            "sp500": 1,
            "policy_rate": 0,
        }

    idx = _make_monthly_index(start=start, periods=n_months)
    rng = np.random.default_rng(42)
    data = pd.DataFrame(
        {v: 100 + rng.standard_normal(n_months).cumsum() for v in variables},
        index=idx,
    )
    data.index.name = "date"

    first_avail = {col: data[col].first_valid_index() for col in data.columns}

    return MacroPanel(
        data=data,
        metadata={v: {"description": f"test {v}"} for v in variables},
        publication_lags=lags,
        first_available=first_avail,
        last_updated=datetime.now(),
    )


# ---------------------------------------------------------------------------
# Panel basics
# ---------------------------------------------------------------------------


class TestPanelLoads:
    def test_panel_has_expected_columns(self) -> None:
        panel = _make_panel()
        assert "cpi" in panel.data.columns
        assert "brent_crude" in panel.data.columns

    def test_panel_targets(self) -> None:
        panel = _make_panel()
        targets = panel.targets()
        assert "cpi" in targets
        assert "industrial_production" in targets
        # Covariates should not be in targets
        assert "brent_crude" not in targets

    def test_panel_covariates(self) -> None:
        panel = _make_panel()
        covs = panel.covariates()
        assert "brent_crude" in covs
        assert "sp500" in covs
        assert "cpi" not in covs

    def test_panel_summary(self) -> None:
        panel = _make_panel()
        s = panel.summary()
        assert "MacroPanel" in s
        assert "cpi" in s

    def test_panel_index_is_monthly(self) -> None:
        panel = _make_panel()
        # All dates should be end-of-month
        for ts in panel.data.index:
            assert ts == ts + pd.offsets.MonthEnd(0)


# ---------------------------------------------------------------------------
# available_at — pseudo-real-time discipline
# ---------------------------------------------------------------------------


class TestAvailableAt:
    def test_respects_lags(self) -> None:
        """Data at forecast origin t does not include series published after t."""
        panel = _make_panel(start="2005-01", n_months=120)

        # At 2010-06-15, CPI (lag=10) for May 2010 is published ~Jun 10.
        # So May's CPI should be available.
        origin = date(2010, 6, 15)
        available = panel.available_at(origin)
        assert "cpi" in available.columns
        cpi_last = available["cpi"].last_valid_index()
        assert cpi_last is not None
        assert cpi_last <= pd.Timestamp("2010-05-31")

    def test_short_lag_excludes_recent(self) -> None:
        """At origin just after month-end, series with longer lags miss latest month."""
        panel = _make_panel(start="2005-01", n_months=120)

        # At 2010-06-05 (5 days into June):
        #   CPI (lag=10): cutoff = May 26. Last obs at-or-before: Apr 30.
        #   policy_rate (lag=0): cutoff = Jun 5. Last obs: May 31.
        origin = date(2010, 6, 5)
        available = panel.available_at(origin)

        cpi_last = available["cpi"].last_valid_index()
        pr_last = available["policy_rate"].last_valid_index()
        assert cpi_last is not None and pr_last is not None
        assert cpi_last <= pd.Timestamp("2010-04-30")
        assert pr_last <= pd.Timestamp("2010-05-31")

    def test_no_future_leakage(self) -> None:
        """No variable has observations beyond what's available at the origin."""
        panel = _make_panel(start="2005-01", n_months=120)
        origin = date(2010, 6, 15)
        available = panel.available_at(origin)

        for col in available.columns:
            last_obs = available[col].last_valid_index()
            if last_obs is None:
                continue
            lag = panel.publication_lags.get(col, 30)
            pub_date = last_obs + pd.Timedelta(days=lag)
            assert pub_date <= pd.Timestamp(origin), (
                f"{col}: last obs {last_obs.date()} published {pub_date.date()}, "
                f"after origin {origin}"
            )

    def test_empty_panel(self) -> None:
        """available_at on empty panel returns empty DataFrame."""
        panel = MacroPanel(
            data=pd.DataFrame(),
            metadata={},
            publication_lags={},
            first_available={},
            last_updated=datetime.now(),
        )
        result = panel.available_at(date(2020, 1, 1))
        assert result.empty


# ---------------------------------------------------------------------------
# Transformation utilities
# ---------------------------------------------------------------------------


class TestTransformations:
    def test_log_diff(self) -> None:
        s = pd.Series([100, 101, 102.01], name="x")
        result = log_diff(s)
        assert result.name == "x_logdiff"
        assert pd.isna(result.iloc[0])
        assert abs(result.iloc[1] - np.log(101 / 100)) < 1e-10

    def test_pct_change_12(self) -> None:
        idx = _make_monthly_index(periods=24)
        # Linear series: 100, 101, 102, ...
        s = pd.Series(range(100, 124), index=idx, name="x")
        result = pct_change(s, periods=12)
        assert result.name == "x_pct12"
        # First 12 values should be NaN
        assert result.iloc[:12].isna().all()
        # Month 12: (112-100)/100 * 100 = 12.0
        assert abs(result.iloc[12] - 12.0) < 1e-10

    def test_standardize(self) -> None:
        rng = np.random.default_rng(42)
        s = pd.Series(rng.standard_normal(100), name="x")
        result = standardize(s, window=50)
        assert result.name == "x_std"
        # After enough observations, z-scores should have mean ~0, std ~1
        tail = result.iloc[60:]
        assert abs(tail.mean()) < 0.5
        assert abs(tail.std() - 1.0) < 0.5

    def test_ma(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], name="x")
        result = ma(s, window=3)
        assert result.name == "x_ma3"
        assert abs(result.iloc[2] - 2.0) < 1e-10  # (1+2+3)/3
        assert abs(result.iloc[4] - 4.0) < 1e-10  # (3+4+5)/3


# ---------------------------------------------------------------------------
# Frequency alignment
# ---------------------------------------------------------------------------


class TestFrequencyAlignment:
    def test_daily_to_monthly(self) -> None:
        idx = pd.date_range("2020-01-01", "2020-03-31", freq="D")
        s = pd.Series(np.ones(len(idx)), index=idx, name="x")
        result = daily_to_monthly(s)
        assert len(result) == 3
        assert all(result == 1.0)
        # Index should be month-end
        assert result.index[0] == pd.Timestamp("2020-01-31")

    def test_quarterly_to_monthly(self) -> None:
        idx = pd.to_datetime(["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31"])
        s = pd.Series([100, 200, 300, 400], index=idx, name="x")
        result = quarterly_to_monthly(s)
        # Should have monthly dates from Mar to Dec
        assert len(result) == 10  # Mar-Dec
        # April should be forward-filled from March
        assert result.loc["2020-04-30"] == 100
        # July should be forward-filled from June
        assert result.loc["2020-07-31"] == 200


# ---------------------------------------------------------------------------
# SSB time parsing
# ---------------------------------------------------------------------------


class TestSSBTimeParsing:
    def test_monthly(self) -> None:
        assert _parse_ssb_time("2020M01") == pd.Timestamp("2020-01-31")
        assert _parse_ssb_time("2020M12") == pd.Timestamp("2020-12-31")

    def test_quarterly(self) -> None:
        assert _parse_ssb_time("2020K1") == pd.Timestamp("2020-03-31")
        assert _parse_ssb_time("2020K4") == pd.Timestamp("2020-12-31")

    def test_annual(self) -> None:
        assert _parse_ssb_time("2020") == pd.Timestamp("2020-12-31")


# ---------------------------------------------------------------------------
# Validation / test origins
# ---------------------------------------------------------------------------


class TestValidationOrigins:
    def test_correct_count_and_range(self) -> None:
        """Correct number of origins over 2006-01 to 2015-12."""
        panel = _make_panel(start="2000-01", n_months=240)
        origins = build_validation_origins(panel, start="2006-01", end="2015-12")
        # 10 years × 12 months = 120 origins
        assert len(origins) == 120
        assert origins[0].origin_date == date(2006, 1, 31)
        assert origins[-1].origin_date == date(2015, 12, 31)

    def test_origins_have_actuals(self) -> None:
        panel = _make_panel(start="2000-01", n_months=240)
        origins = build_validation_origins(panel, start="2006-01", end="2008-12")
        for origin in origins:
            # Each origin should have actuals for at least some targets
            assert len(origin.actuals) > 0
            for var, series in origin.actuals.items():
                for h in series.index:
                    assert h in HORIZONS

    def test_available_data_respects_origin(self) -> None:
        panel = _make_panel(start="2000-01", n_months=240)
        origins = build_validation_origins(panel, start="2010-01", end="2010-03")
        for origin in origins:
            for col in origin.available_data.columns:
                last_obs = origin.available_data[col].last_valid_index()
                if last_obs is None:
                    continue
                lag = panel.publication_lags.get(col, 30)
                pub_date = last_obs + pd.Timedelta(days=lag)
                assert pub_date <= pd.Timestamp(origin.origin_date)

    def test_step_months(self) -> None:
        panel = _make_panel(start="2000-01", n_months=240)
        origins = build_validation_origins(
            panel, start="2006-01", end="2015-12", step_months=3
        )
        # 10 years × 4 quarters = 40 origins
        assert len(origins) == 40


class TestTestOrigins:
    def test_starts_at_2016(self) -> None:
        panel = _make_panel(start="2000-01", n_months=240)
        origins = build_test_origins(panel, start="2016-01", end="2016-06")
        assert origins[0].origin_date == date(2016, 1, 31)
        assert len(origins) == 6


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_rmse_perfect(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        assert rmse(a, a) == 0.0

    def test_rmse_known(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        p = np.array([1.0, 2.0, 4.0])
        expected = np.sqrt(1 / 3)
        assert abs(rmse(a, p) - expected) < 1e-10

    def test_mae_perfect(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        assert mae(a, a) == 0.0

    def test_mae_known(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        p = np.array([0.0, 2.0, 5.0])
        assert abs(mae(a, p) - 1.0) < 1e-10

    def test_mase(self) -> None:
        a = np.array([1.0, 2.0, 3.0])
        p = np.array([1.5, 2.5, 3.5])
        naive_err = np.array([1.0, 1.0])  # naive errors of 1.0 each
        result = mase(a, p, naive_err)
        # MAE = 0.5, naive MAE = 1.0 → MASE = 0.5
        assert abs(result - 0.5) < 1e-10

    def test_mase_zero_naive(self) -> None:
        a = np.array([1.0, 2.0])
        p = np.array([1.5, 2.5])
        naive_err = np.array([0.0, 0.0])
        assert mase(a, p, naive_err) == np.inf

    def test_pinball_loss(self) -> None:
        actual = np.array([1.0, 2.0, 3.0])
        # Perfect quantile forecast
        quantiles = actual[:, np.newaxis]
        levels = np.array([0.5])
        assert abs(pinball_loss(actual, quantiles, levels)) < 1e-10

    def test_pinball_loss_asymmetry(self) -> None:
        actual = np.array([2.0])
        # Forecast below actual → positive error
        quantiles = np.array([[1.0]])
        # At tau=0.9, underprediction is penalized more
        levels_high = np.array([0.9])
        loss_high = pinball_loss(actual, quantiles, levels_high)
        # At tau=0.1, underprediction is penalized less
        levels_low = np.array([0.1])
        loss_low = pinball_loss(actual, quantiles, levels_low)
        assert loss_high > loss_low


# ---------------------------------------------------------------------------
# Evaluate forecasts end-to-end
# ---------------------------------------------------------------------------


class TestEvaluateForecasts:
    def test_perfect_forecast(self) -> None:
        panel = _make_panel(start="2000-01", n_months=240)
        origins = build_validation_origins(panel, start="2006-01", end="2006-06")

        # Build "perfect" forecasts from actuals
        forecasts: dict[str, pd.DataFrame] = {}
        for var in panel.targets():
            rows: dict[date, dict[int, float]] = {}
            for origin in origins:
                if var in origin.actuals:
                    rows[origin.origin_date] = origin.actuals[var].to_dict()
            if rows:
                forecasts[var] = pd.DataFrame.from_dict(rows, orient="index")

        results = evaluate_forecasts(forecasts, origins)
        for var in results:
            for h in results[var]:
                assert results[var][h]["rmse"] < 1e-10
                assert results[var][h]["mae"] < 1e-10


# ---------------------------------------------------------------------------
# Publication lags config
# ---------------------------------------------------------------------------


class TestPublicationLags:
    def test_loads_from_yaml(self) -> None:
        lags = load_publication_lags()
        assert isinstance(lags, dict)
        assert "cpi" in lags
        assert lags["cpi"] == 10
        assert lags["policy_rate"] == 0


# ---------------------------------------------------------------------------
# JSON-stat2 parser
# ---------------------------------------------------------------------------


class TestJsonStat2Parser:
    def test_simple_timeseries(self) -> None:
        """Parse a minimal JSON-stat2 dataset."""
        from prepare import _parse_jsonstat2

        data = {
            "version": "2.0",
            "class": "dataset",
            "id": ["ContentsCode", "Tid"],
            "size": [1, 3],
            "dimension": {
                "ContentsCode": {
                    "category": {
                        "index": {"KPI": 0},
                        "label": {"KPI": "CPI"},
                    }
                },
                "Tid": {
                    "category": {
                        "index": {"2020M01": 0, "2020M02": 1, "2020M03": 2},
                        "label": {
                            "2020M01": "2020M01",
                            "2020M02": "2020M02",
                            "2020M03": "2020M03",
                        },
                    }
                },
            },
            "value": [1.5, 1.6, 1.7],
        }
        series = _parse_jsonstat2(data)
        assert len(series) == 3
        assert series.iloc[0] == 1.5
        assert series.index[0] == pd.Timestamp("2020-01-31")
        assert series.index[2] == pd.Timestamp("2020-03-31")

    def test_quarterly_timeseries(self) -> None:
        from prepare import _parse_jsonstat2

        data = {
            "version": "2.0",
            "class": "dataset",
            "id": ["Tid"],
            "size": [2],
            "dimension": {
                "Tid": {
                    "category": {
                        "index": {"2020K1": 0, "2020K2": 1},
                        "label": {"2020K1": "2020K1", "2020K2": "2020K2"},
                    }
                },
            },
            "value": [100.0, 105.0],
        }
        series = _parse_jsonstat2(data)
        assert len(series) == 2
        assert series.index[0] == pd.Timestamp("2020-03-31")
        assert series.index[1] == pd.Timestamp("2020-06-30")

    def test_null_values(self) -> None:
        from prepare import _parse_jsonstat2

        data = {
            "version": "2.0",
            "class": "dataset",
            "id": ["Tid"],
            "size": [3],
            "dimension": {
                "Tid": {
                    "category": {
                        "index": {"2020M01": 0, "2020M02": 1, "2020M03": 2},
                        "label": {
                            "2020M01": "2020M01",
                            "2020M02": "2020M02",
                            "2020M03": "2020M03",
                        },
                    }
                },
            },
            "value": [1.0, None, 3.0],
        }
        series = _parse_jsonstat2(data)
        assert pd.isna(series.iloc[1])
        assert series.iloc[2] == 3.0


class TestFfillHardening:
    """ffill_covariates_only + warn_if_targets_stale."""

    def _panel(self) -> pd.DataFrame:
        idx = pd.date_range("2025-06-30", periods=11, freq="ME")
        return pd.DataFrame({
            "cpi": [2.1, 2.3, 2.5, 2.4, 2.6, 2.5, 2.7] + [np.nan] * 4,
            "policy_rate": [4.5, 4.5, np.nan, 4.25, 4.25, np.nan, np.nan, 4.0, np.nan, np.nan, 3.75],
            "unemployment": [6.2, 6.1, 6.0, 6.1, 6.0, 6.2, 6.1, 6.0] + [np.nan] * 3,
        }, index=idx)

    def test_targets_keep_trailing_nan(self) -> None:
        out = ffill_covariates_only(self._panel())
        # Last real values for targets are preserved at Dec 2025 / Jan 2026
        assert out["cpi"].notna().sum() == 7
        assert out["unemployment"].notna().sum() == 8
        # Trailing NaN on targets is NOT ffilled away
        assert out["cpi"].iloc[-1] is np.nan or pd.isna(out["cpi"].iloc[-1])
        assert pd.isna(out["unemployment"].iloc[-1])

    def test_covariates_are_ffilled(self) -> None:
        out = ffill_covariates_only(self._panel())
        # Every covariate cell after the first real obs is non-NaN
        assert out["policy_rate"].isna().sum() == 0
        # And values propagate forward, not backward
        assert out["policy_rate"].iloc[2] == 4.5  # gap filled with prior
        assert out["policy_rate"].iloc[-1] == 3.75

    def test_no_mutation_of_input(self) -> None:
        df = self._panel()
        before = df.copy()
        ffill_covariates_only(df)
        pd.testing.assert_frame_equal(df, before)

    def test_warn_fires_for_stale_target(self, caplog) -> None:
        import logging
        caplog.set_level(logging.WARNING, logger="prepare")
        warn_if_targets_stale(ffill_covariates_only(self._panel()), stale_threshold_months=3)
        messages = [r.getMessage() for r in caplog.records]
        # cpi is 4 months behind panel_end (2026-04-30); unemployment is 3 → not stale
        assert any("'cpi'" in m and "behind panel end" in m for m in messages)
        assert not any("'unemployment'" in m for m in messages)

    def test_warn_silent_when_all_fresh(self, caplog) -> None:
        import logging
        caplog.set_level(logging.WARNING, logger="prepare")
        fresh = self._panel()
        # Replace trailing NaN with real values so every target is current
        fresh["cpi"] = fresh["cpi"].ffill()
        fresh["unemployment"] = fresh["unemployment"].ffill()
        warn_if_targets_stale(fresh, stale_threshold_months=3)
        assert not any("behind panel end" in r.getMessage() for r in caplog.records)
