"""Tests for the Chronos-2 training scaffold (train.py).

Tests the dataset builder, config, and transformation pipeline
without requiring GPU or ML dependencies.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from prepare import ForecastOrigin, MacroPanel

# Import train.py components that don't require ML deps
from train import (
    TRANSFORM_FUNCTIONS,
    apply_transforms,
    build_ag_dataset,
    get_current_config,
)


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
                      "brent_crude", "sp500"]
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


def _make_origin(panel: MacroPanel, origin_date: date) -> ForecastOrigin:
    available = panel.available_at(origin_date)
    origin_ts = pd.Timestamp(origin_date)
    actuals: dict[str, pd.Series] = {}
    for var in panel.targets():
        if var not in panel.data.columns:
            continue
        horizon_vals: dict[int, float] = {}
        for h in [1, 3, 6, 12]:
            target_date = origin_ts + pd.DateOffset(months=h) + pd.offsets.MonthEnd(0)
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
# Tests: Dataset Builder
# ---------------------------------------------------------------------------


class TestBuildAgDataset:
    def test_basic_univariate(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        df = build_ag_dataset(origin.available_data, ["cpi"], [], context_length=None)

        assert "item_id" in df.columns
        assert "timestamp" in df.columns
        assert "target" in df.columns
        assert (df["item_id"] == "cpi").all()
        assert len(df) > 0

    def test_multiple_targets(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        targets = ["cpi", "unemployment"]
        df = build_ag_dataset(origin.available_data, targets, [], context_length=None)

        item_ids = df["item_id"].unique()
        assert set(item_ids) == set(targets)

    def test_with_covariates(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        df = build_ag_dataset(
            origin.available_data, ["cpi"], ["brent_crude", "sp500"],
            context_length=None,
        )

        assert "brent_crude" in df.columns
        assert "sp500" in df.columns

    def test_context_length_truncation(self):
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        df_full = build_ag_dataset(origin.available_data, ["cpi"], [], context_length=None)
        df_short = build_ag_dataset(origin.available_data, ["cpi"], [], context_length=24)

        assert len(df_short) <= 24
        assert len(df_short) < len(df_full)

    def test_empty_data_returns_empty(self):
        empty_data = pd.DataFrame()
        df = build_ag_dataset(empty_data, ["cpi"], [], context_length=None)
        assert df.empty

    def test_missing_target_skipped(self):
        panel = _make_panel(variables=["cpi", "brent_crude"])
        origin = _make_origin(panel, date(2010, 6, 15))
        df = build_ag_dataset(
            origin.available_data, ["cpi", "nonexistent"], [],
            context_length=None,
        )
        assert set(df["item_id"].unique()) == {"cpi"}


# ---------------------------------------------------------------------------
# Tests: Transformations
# ---------------------------------------------------------------------------


class TestTransformations:
    def test_all_transforms_registered(self):
        expected = ["none", "log_diff", "pct_change_12", "pct_change_1",
                    "standardize_60", "ma_3", "ma_6"]
        for name in expected:
            assert name in TRANSFORM_FUNCTIONS

    def test_apply_transforms_no_config(self):
        """With empty TRANSFORMS dict, data should pass through unchanged."""
        import train
        old_transforms = train.TRANSFORMS
        try:
            train.TRANSFORMS = {}
            data = pd.DataFrame({"cpi": [1.0, 2.0, 3.0]})
            result = apply_transforms(data)
            pd.testing.assert_frame_equal(result, data)
        finally:
            train.TRANSFORMS = old_transforms

    def test_apply_transforms_with_config(self):
        import train
        old_transforms = train.TRANSFORMS
        try:
            train.TRANSFORMS = {"cpi": "ma_3"}
            data = pd.DataFrame({
                "cpi": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "other": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
            })
            result = apply_transforms(data)
            # other column unchanged
            pd.testing.assert_series_equal(result["other"], data["other"])
            # cpi column is now moving average
            assert result["cpi"].iloc[-1] == pytest.approx(5.0)  # ma(3) of [4,5,6]
        finally:
            train.TRANSFORMS = old_transforms


# ---------------------------------------------------------------------------
# Tests: Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_get_current_config(self):
        config = get_current_config()
        assert "model_path" in config
        assert "covariates" in config
        assert "fine_tune" in config
        assert "prediction_length" in config

    def test_config_captures_values(self):
        import train
        old_covs = train.COVARIATES
        try:
            train.COVARIATES = ["brent_crude", "vix"]
            config = get_current_config()
            assert config["covariates"] == ["brent_crude", "vix"]
        finally:
            train.COVARIATES = old_covs


# ---------------------------------------------------------------------------
# Tests: Model (requires ML deps — skip if not installed)
# ---------------------------------------------------------------------------


class TestModelIntegration:
    @pytest.fixture(autouse=True)
    def _check_autogluon(self):
        pytest.importorskip("autogluon.timeseries")

    def test_fit_predictor(self):
        from train import fit_predictor
        panel = _make_panel()
        origin = _make_origin(panel, date(2010, 6, 15))
        predictor = fit_predictor(
            origin.available_data,
            targets=["cpi"],
            covariates=[],
        )
        assert predictor is not None
