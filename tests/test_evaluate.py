"""Tests for the evaluation harness (evaluate.py)."""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from evaluate import (
    EvaluationResult,
    ForecastResult,
    compare_methods,
    evaluate,
    format_results_table,
    load_eval_result,
    relative_metrics,
    save_result,
)
from prepare import (
    HORIZONS,
    ForecastOrigin,
    MacroPanel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_monthly_index(start: str = "1995-01", periods: int = 360) -> pd.DatetimeIndex:
    return pd.date_range(start=start, periods=periods, freq="ME")


def _make_panel(
    variables: list[str] | None = None,
    start: str = "1995-01",
    periods: int = 360,
) -> MacroPanel:
    if variables is None:
        variables = ["cpi", "industrial_production", "retail_sales", "unemployment",
                      "brent_crude", "sp500"]
    idx = _make_monthly_index(start, periods)
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


def _make_perfect_forecasts(
    panel: MacroPanel,
    origins: list[ForecastOrigin],
    horizons: list[int],
) -> dict[str, pd.DataFrame]:
    """Create perfect (oracle) forecasts from the panel."""
    forecasts: dict[str, pd.DataFrame] = {}
    targets = panel.targets()
    for var in targets:
        rows = {}
        for origin in origins:
            if var in origin.actuals:
                row = {}
                for h in horizons:
                    if h in origin.actuals[var].index:
                        row[h] = origin.actuals[var][h]
                if row:
                    rows[origin.origin_date] = row
        if rows:
            forecasts[var] = pd.DataFrame.from_dict(rows, orient="index")
    return forecasts


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestForecastResult:
    def test_create_basic(self):
        fr = ForecastResult(
            method_name="test",
            point_forecasts={"cpi": pd.DataFrame({1: [1.0], 3: [2.0]})},
        )
        assert fr.method_name == "test"
        assert fr.era == "validation"
        assert fr.horizons == list(HORIZONS)

    def test_with_config(self):
        fr = ForecastResult(
            method_name="test",
            point_forecasts={},
            config={"lr": 0.01, "covariates": ["brent"]},
        )
        assert fr.config["lr"] == 0.01


class TestEvaluate:
    def test_perfect_forecast_gives_zero_error(self):
        panel = _make_panel()
        from prepare import build_validation_origins
        origins = build_validation_origins(panel, horizons=[1, 3])
        forecasts = _make_perfect_forecasts(panel, origins, [1, 3])

        fr = ForecastResult(
            method_name="oracle",
            point_forecasts=forecasts,
            horizons=[1, 3],
        )
        result = evaluate(fr, panel)

        for var in result.metrics:
            for h in result.metrics[var]:
                assert result.metrics[var][h]["rmse"] < 1e-10
                assert result.metrics[var][h]["mae"] < 1e-10

    def test_summary_aggregates_targets(self):
        panel = _make_panel()
        from prepare import build_validation_origins
        origins = build_validation_origins(panel, horizons=[1])
        forecasts = _make_perfect_forecasts(panel, origins, [1])

        fr = ForecastResult(
            method_name="oracle",
            point_forecasts=forecasts,
            horizons=[1],
        )
        result = evaluate(fr, panel)

        assert 1 in result.summary
        assert result.summary[1]["n_variables"] > 0

    def test_noisy_forecast_has_positive_error(self):
        panel = _make_panel()
        from prepare import build_validation_origins
        origins = build_validation_origins(panel, horizons=[1])
        forecasts = _make_perfect_forecasts(panel, origins, [1])

        # Add noise
        rng = np.random.default_rng(99)
        for var, df in forecasts.items():
            forecasts[var] = df + rng.standard_normal(df.shape) * 5

        fr = ForecastResult(
            method_name="noisy",
            point_forecasts=forecasts,
            horizons=[1],
        )
        result = evaluate(fr, panel)

        for var in result.metrics:
            for h in result.metrics[var]:
                assert result.metrics[var][h]["rmse"] > 0


class TestSaveAndLoad:
    def test_roundtrip(self, tmp_path):
        panel = _make_panel()
        from prepare import build_validation_origins
        origins = build_validation_origins(panel, horizons=[1, 3])
        forecasts = _make_perfect_forecasts(panel, origins, [1, 3])

        fr = ForecastResult(
            method_name="test_method",
            point_forecasts=forecasts,
            config={"some": "config"},
            horizons=[1, 3],
        )
        eval_result = evaluate(fr, panel)
        out_dir = save_result(fr, eval_result, base_dir=tmp_path)

        # Check files exist
        assert (out_dir / "config.json").exists()
        assert (out_dir / "metrics.json").exists()
        assert (out_dir / "summary.txt").exists()
        assert (out_dir / "point_forecasts.parquet").exists()

        # Load and compare
        loaded = load_eval_result(out_dir)
        assert loaded.method_name == "test_method"
        assert loaded.era == "validation"
        assert set(loaded.metrics.keys()) == set(eval_result.metrics.keys())

    def test_config_preserved(self, tmp_path):
        fr = ForecastResult(
            method_name="cfg_test",
            point_forecasts={"cpi": pd.DataFrame({1: [1.0]})},
            config={"lr": 0.01, "covariates": ["brent", "vix"]},
            horizons=[1],
        )
        # Minimal eval result
        eval_result = EvaluationResult(
            method_name="cfg_test",
            era="validation",
            metrics={},
            subperiod_metrics={},
            summary={},
        )
        out_dir = save_result(fr, eval_result, base_dir=tmp_path)

        config = json.loads((out_dir / "config.json").read_text())
        assert config["config"]["lr"] == 0.01
        assert config["config"]["covariates"] == ["brent", "vix"]


class TestFormatting:
    def test_format_table_runs(self):
        eval_result = EvaluationResult(
            method_name="test",
            era="validation",
            metrics={
                "cpi": {1: {"rmse": 0.5, "mae": 0.4, "mase": 0.8, "n_origins": 100}},
            },
            subperiod_metrics={},
            summary={1: {"avg_rmse": 0.5, "avg_mae": 0.4, "avg_mase": 0.8, "n_variables": 1}},
        )
        text = format_results_table(eval_result)
        assert "test" in text
        assert "cpi" in text
        assert "0.5000" in text


class TestComparison:
    def test_compare_two_methods(self):
        r1 = EvaluationResult(
            method_name="method_a",
            era="validation",
            metrics={"cpi": {1: {"rmse": 0.5, "mae": 0.4, "mase": 0.8}}},
            subperiod_metrics={},
            summary={1: {"avg_rmse": 0.5, "avg_mae": 0.4, "avg_mase": 0.8}},
        )
        r2 = EvaluationResult(
            method_name="method_b",
            era="validation",
            metrics={"cpi": {1: {"rmse": 0.3, "mae": 0.2, "mase": 0.5}}},
            subperiod_metrics={},
            summary={1: {"avg_rmse": 0.3, "avg_mae": 0.2, "avg_mase": 0.5}},
        )
        text = compare_methods([r1, r2], metric="rmse")
        assert "method_a" in text
        assert "method_b" in text

    def test_relative_metrics(self):
        baseline = EvaluationResult(
            method_name="baseline",
            era="validation",
            metrics={"cpi": {1: {"rmse": 1.0}}},
            subperiod_metrics={},
            summary={},
        )
        result = EvaluationResult(
            method_name="improved",
            era="validation",
            metrics={"cpi": {1: {"rmse": 0.8}}},
            subperiod_metrics={},
            summary={},
        )
        ratios = relative_metrics(result, baseline, metric="rmse")
        assert abs(ratios["cpi"][1] - 0.8) < 1e-10

    def test_relative_metrics_worse(self):
        baseline = EvaluationResult(
            method_name="baseline",
            era="validation",
            metrics={"cpi": {1: {"rmse": 1.0}}},
            subperiod_metrics={},
            summary={},
        )
        result = EvaluationResult(
            method_name="worse",
            era="validation",
            metrics={"cpi": {1: {"rmse": 1.5}}},
            subperiod_metrics={},
            summary={},
        )
        ratios = relative_metrics(result, baseline, metric="rmse")
        assert ratios["cpi"][1] > 1.0
