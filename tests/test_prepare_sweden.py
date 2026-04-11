"""Tests for the Sweden data pipeline.

Uses synthetic data and mocked API responses — no network calls.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prepare import MacroPanel


def _make_panel_sweden() -> MacroPanel:
    """Create a synthetic Sweden-like MacroPanel for testing.

    Mirrors what build_panel_sweden() actually produces, including the
    DROPPED_VARIABLES filter (currently drops retail_sales — see
    metadata/sweden_target_notes.md).
    """
    rng = np.random.default_rng(42)
    dates = pd.date_range("2000-01-31", "2025-12-31", freq="ME")
    n = len(dates)

    # retail_sales is intentionally absent: SCB does not publish a long
    # enough history for the validation era.
    targets = ["cpi", "industrial_production", "unemployment"]
    covariates = [
        "house_prices", "credit", "exports", "imports",
        "policy_rate", "fx_eur", "fx_usd",
        "brent_crude", "sp500", "fed_funds", "us_cpi",
        "euro_area_gdp", "vix", "global_epu",
    ]

    data = {}
    for var in targets + covariates:
        data[var] = 100 + rng.normal(0, 1, n).cumsum()

    df = pd.DataFrame(data, index=dates)
    df.index.name = "date"

    pub_lags = {var: 30 for var in targets + covariates}
    pub_lags["policy_rate"] = 0
    pub_lags["fx_eur"] = 1
    pub_lags["fx_usd"] = 1

    first_available = {col: df[col].first_valid_index() for col in df.columns}

    from datetime import datetime
    return MacroPanel(
        data=df,
        metadata={var: {"source": "synthetic"} for var in targets + covariates},
        publication_lags=pub_lags,
        first_available=first_available,
        last_updated=datetime.now(),
    )


class TestSwedenPanelStructure:
    """Test that a Sweden panel has the expected structure."""

    def test_has_three_targets(self) -> None:
        # Sweden has only three targets — retail_sales is dropped because the
        # SCB table we know about lacks a validation-era history.
        panel = _make_panel_sweden()
        targets = panel.targets()
        assert set(targets) == {"cpi", "industrial_production", "unemployment"}
        assert "retail_sales" not in targets

    def test_has_fx_covariates(self) -> None:
        panel = _make_panel_sweden()
        covs = panel.covariates()
        assert "fx_eur" in covs
        assert "fx_usd" in covs

    def test_has_policy_rate(self) -> None:
        panel = _make_panel_sweden()
        assert "policy_rate" in panel.covariates()

    def test_available_at_respects_lags(self) -> None:
        from datetime import date
        panel = _make_panel_sweden()
        available = panel.available_at(date(2020, 6, 30))
        # Policy rate has 0 lag, so data up to June 2020
        assert available["policy_rate"].index[-1] >= pd.Timestamp("2020-06-30")
        # CPI has 30-day lag, so data up to ~May 2020
        assert available["cpi"].index[-1] <= pd.Timestamp("2020-06-30")

    def test_panel_has_17_variables(self) -> None:
        panel = _make_panel_sweden()
        assert len(panel.data.columns) == 17  # 3 targets + 14 covariates


class TestSCBJsonStat2Parsing:
    """Test that SCB json-stat2 parsing works like SSB."""

    def test_parse_jsonstat2_scb_format(self) -> None:
        """SCB uses the same json-stat2 format as SSB."""
        from prepare import _parse_jsonstat2

        # Minimal json-stat2 response (same format as SSB)
        data = {
            "version": "2.0",
            "class": "dataset",
            "id": ["ContentsCode", "Tid"],
            "size": [1, 3],
            "dimension": {
                "ContentsCode": {
                    "category": {
                        "index": {"000004VV": 0},
                        "label": {"000004VV": "Annual changes"},
                    }
                },
                "Tid": {
                    "category": {
                        "index": {"0": 0, "1": 1, "2": 2},
                        "label": {"0": "2020M01", "1": "2020M02", "2": "2020M03"},
                    }
                },
            },
            "value": [1.5, 1.8, 2.0],
        }

        series = _parse_jsonstat2(data)
        assert len(series) == 3
        assert series.iloc[0] == pytest.approx(1.5)
        assert series.iloc[2] == pytest.approx(2.0)


class TestRiksbankParsing:
    """Test Riksbank API response parsing."""

    def test_parse_riksbank_daily_to_monthly(self) -> None:
        """Riksbank daily data converts to monthly averages."""
        from prepare import daily_to_monthly

        dates = pd.date_range("2020-01-01", "2020-03-31", freq="B")
        values = np.random.default_rng(42).uniform(9, 11, len(dates))
        daily = pd.Series(values, index=dates, name="fx_eur")

        monthly = daily_to_monthly(daily)
        assert len(monthly) == 3  # Jan, Feb, Mar
        assert monthly.index[-1] == pd.Timestamp("2020-03-31")
