"""Tests for the Canada data pipeline.

Uses synthetic data — no network calls.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from prepare import MacroPanel


def _make_panel_canada() -> MacroPanel:
    """Create a synthetic Canada-like MacroPanel for testing."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2000-01-31", "2025-12-31", freq="ME")
    n = len(dates)

    targets = ["cpi", "industrial_production", "retail_sales", "unemployment"]
    covariates = [
        "house_prices", "credit", "exports", "imports",
        "policy_rate", "fx_usd", "fx_eur",
        "brent_crude", "sp500", "fed_funds", "us_cpi",
        "euro_area_gdp", "vix", "global_epu", "partner_activity",
    ]

    data = {}
    for var in targets + covariates:
        data[var] = 100 + rng.normal(0, 1, n).cumsum()

    df = pd.DataFrame(data, index=dates)
    df.index.name = "date"

    pub_lags = {var: 30 for var in targets + covariates}
    pub_lags["cpi"] = 18
    pub_lags["unemployment"] = 8
    pub_lags["industrial_production"] = 60
    pub_lags["policy_rate"] = 0
    pub_lags["fx_usd"] = 1
    pub_lags["fx_eur"] = 1

    first_available = {col: df[col].first_valid_index() for col in df.columns}

    return MacroPanel(
        data=df,
        metadata={var: {"source": "synthetic"} for var in targets + covariates},
        publication_lags=pub_lags,
        first_available=first_available,
        last_updated=datetime.now(),
    )


class TestCanadaPanelStructure:
    """Test that a Canada panel has the expected structure."""

    def test_has_all_four_targets(self) -> None:
        panel = _make_panel_canada()
        targets = panel.targets()
        assert "cpi" in targets
        assert "industrial_production" in targets
        assert "retail_sales" in targets
        assert "unemployment" in targets

    def test_has_partner_activity(self) -> None:
        panel = _make_panel_canada()
        assert "partner_activity" in panel.covariates()

    def test_has_fx_covariates(self) -> None:
        panel = _make_panel_canada()
        covs = panel.covariates()
        assert "fx_usd" in covs
        assert "fx_eur" in covs

    def test_canada_specific_lags(self) -> None:
        panel = _make_panel_canada()
        assert panel.publication_lags["cpi"] == 18
        assert panel.publication_lags["unemployment"] == 8
        assert panel.publication_lags["industrial_production"] == 60


class TestStatCanCSVParsing:
    """Test Statistics Canada CSV parsing logic."""

    def test_parse_statcan_series_basic(self) -> None:
        """Test filtering a synthetic StatCan-style DataFrame."""
        from prepare_canada import parse_statcan_series

        df = pd.DataFrame({
            "REF_DATE": ["2020-01", "2020-02", "2020-03", "2020-01", "2020-02", "2020-03"],
            "GEO": ["Canada"] * 3 + ["Ontario"] * 3,
            "Labour force characteristics": ["Unemployment rate"] * 6,
            "VALUE": [5.5, 5.7, 6.0, 6.1, 6.3, 6.5],
        })

        config = {
            "filters": {
                "GEO": "Canada",
                "Labour force characteristics": "Unemployment rate",
            },
            "value_column": "VALUE",
        }

        series = parse_statcan_series(df, config)
        assert series is not None
        assert len(series) == 3
        assert series.iloc[0] == pytest.approx(5.5)
        assert series.iloc[2] == pytest.approx(6.0)

    def test_parse_statcan_series_empty_filter(self) -> None:
        """Returns None when no data matches filters."""
        from prepare_canada import parse_statcan_series

        df = pd.DataFrame({
            "REF_DATE": ["2020-01"],
            "GEO": ["Ontario"],
            "VALUE": [5.5],
        })

        config = {"filters": {"GEO": "Canada"}, "value_column": "VALUE"}
        result = parse_statcan_series(df, config)
        assert result is None


class TestBoCParsing:
    """Test Bank of Canada Valet API response parsing."""

    def test_boc_daily_to_monthly(self) -> None:
        """Daily BoC data converts to monthly averages."""
        from prepare import daily_to_monthly

        dates = pd.date_range("2024-01-01", "2024-03-31", freq="B")
        values = np.random.default_rng(42).uniform(1.3, 1.4, len(dates))
        daily = pd.Series(values, index=dates, name="fx_usd")

        monthly = daily_to_monthly(daily)
        assert len(monthly) == 3
        assert monthly.index[-1] == pd.Timestamp("2024-03-31")

    def test_policy_rate_ffill(self) -> None:
        """Policy rate with gaps is forward-filled before monthly aggregation."""
        # Simulate rate that only changes on decision dates
        dates = [pd.Timestamp("2024-01-24"), pd.Timestamp("2024-03-06")]
        values = [5.0, 4.75]
        series = pd.Series(values, index=pd.DatetimeIndex(dates), name="policy_rate")

        # Forward-fill across full daily range
        full_idx = pd.date_range(series.index.min(), "2024-03-31", freq="D")
        filled = series.reindex(full_idx).ffill()

        from prepare import daily_to_monthly
        monthly = daily_to_monthly(filled)
        assert len(monthly) >= 2
        # January should be 5.0
        assert monthly.iloc[0] == pytest.approx(5.0)
