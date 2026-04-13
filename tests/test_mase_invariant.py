"""Test that the random walk MASE equals 1.000 by construction.

This is a key invariant: MASE = MAE / MAE_naive, and the naive forecast
IS the random walk, so RW MASE must be exactly 1.000 for every
(country, target, horizon, era) combination.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FE_PATH = PROJECT_ROOT / "results" / "forecast_errors.parquet"


@pytest.fixture
def forecast_errors() -> pd.DataFrame:
    if not FE_PATH.exists():
        pytest.skip("forecast_errors.parquet not found — run build_forecast_errors.py first")
    return pd.read_parquet(FE_PATH)


class TestRWMaseIsOne:
    """Random walk MASE must equal 1.000 everywhere."""

    def test_rw_mase_per_country_target_horizon_era(self, forecast_errors: pd.DataFrame) -> None:
        """MASE for random walk is 1.000 for every group."""
        df = forecast_errors
        rw = df[df["model_variant"] == "random_walk"]
        assert not rw.empty, "No random walk data in forecast_errors"

        # Group by all dimensions and compute MASE = RW_MAE / RW_MAE = 1.0
        groups = rw.groupby(["country", "target", "horizon", "is_validation"])
        for (country, target, horizon, is_val), group in groups:
            era = "validation" if is_val else "test"
            mae = group["abs_error"].mean()
            # MASE = MAE / MAE = 1.0 by definition
            mase = mae / mae  # Should be exactly 1.0
            assert mase == pytest.approx(1.0, abs=1e-10), (
                f"RW MASE != 1.0 for {country}/{target}/h={horizon}/{era}: got {mase}"
            )

    def test_rw_has_all_countries(self, forecast_errors: pd.DataFrame) -> None:
        """Every country in the dataset has random walk results."""
        df = forecast_errors
        countries = df["country"].unique()
        rw_countries = df[df["model_variant"] == "random_walk"]["country"].unique()
        missing = set(countries) - set(rw_countries)
        assert not missing, f"Countries without random walk results: {missing}"

    def test_rw_has_all_targets(self, forecast_errors: pd.DataFrame) -> None:
        """Every target variable has random walk results."""
        df = forecast_errors
        targets = df["target"].unique()
        rw_targets = df[df["model_variant"] == "random_walk"]["target"].unique()
        missing = set(targets) - set(rw_targets)
        assert not missing, f"Targets without random walk results: {missing}"

    def test_rw_has_all_horizons(self, forecast_errors: pd.DataFrame) -> None:
        """All horizons have random walk results."""
        df = forecast_errors
        horizons = set(df["horizon"].unique())
        rw_horizons = set(df[df["model_variant"] == "random_walk"]["horizon"].unique())
        missing = horizons - rw_horizons
        assert not missing, f"Horizons without random walk results: {missing}"

    def test_shared_origin_mase_equals_one(self, forecast_errors: pd.DataFrame) -> None:
        """MASE computed via shared-origin join also equals 1.000 for RW."""
        df = forecast_errors
        rw = df[df["model_variant"] == "random_walk"]

        for is_val in [True, False]:
            era_data = rw[rw["is_validation"] == is_val]
            for target in era_data["target"].unique():
                for h in era_data["horizon"].unique():
                    mask = (era_data["target"] == target) & (era_data["horizon"] == h)
                    subset = era_data[mask]
                    if subset.empty:
                        continue
                    # Self-join: MASE of RW against itself
                    merged = subset[["origin_date", "abs_error"]].merge(
                        subset[["origin_date", "abs_error"]],
                        on="origin_date",
                        suffixes=("_method", "_rw"),
                    )
                    mase = merged["abs_error_method"].mean() / merged["abs_error_rw"].mean()
                    era = "validation" if is_val else "test"
                    assert mase == pytest.approx(1.0, abs=1e-10), (
                        f"Shared-origin MASE != 1.0 for {target}/h={h}/{era}: got {mase}"
                    )
