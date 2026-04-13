"""Test that table generation is deterministic.

Running generate_tables.py twice must produce identical output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FE_PATH = PROJECT_ROOT / "results" / "forecast_errors.parquet"

# Add src to path so we can import the table generator
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture
def forecast_errors_exist() -> None:
    if not FE_PATH.exists():
        pytest.skip("forecast_errors.parquet not found — run build_forecast_errors.py first")


class TestTableDeterminism:
    """Table generation must be deterministic."""

    def test_validation_table_deterministic(self, forecast_errors_exist: None) -> None:
        from tables.generate_tables import generate_validation_table, load_errors
        df = load_errors()
        run1 = generate_validation_table(df)
        run2 = generate_validation_table(df)
        assert run1 == run2, "Validation table output differs between runs"

    def test_test_table_deterministic(self, forecast_errors_exist: None) -> None:
        from tables.generate_tables import generate_test_table, load_errors
        df = load_errors()
        run1 = generate_test_table(df)
        run2 = generate_test_table(df)
        assert run1 == run2, "Test table output differs between runs"

    def test_subperiod_table_deterministic(self, forecast_errors_exist: None) -> None:
        from tables.generate_tables import generate_subperiod_table, load_errors
        df = load_errors()
        run1 = generate_subperiod_table(df)
        run2 = generate_subperiod_table(df)
        assert run1 == run2, "Subperiod table output differs between runs"

    def test_per_variable_table_deterministic(self, forecast_errors_exist: None) -> None:
        from tables.generate_tables import generate_per_variable_test_table, load_errors
        df = load_errors()
        run1 = generate_per_variable_test_table(df)
        run2 = generate_per_variable_test_table(df)
        assert run1 == run2, "Per-variable table output differs between runs"

    def test_validation_table_not_empty(self, forecast_errors_exist: None) -> None:
        from tables.generate_tables import generate_validation_table, load_errors
        df = load_errors()
        output = generate_validation_table(df)
        assert r"\begin{tabular}" in output
        assert r"\end{tabular}" in output
        assert "Random walk" in output
        assert "1.000" in output

    def test_test_table_not_empty(self, forecast_errors_exist: None) -> None:
        from tables.generate_tables import generate_test_table, load_errors
        df = load_errors()
        output = generate_test_table(df)
        assert r"\begin{tabular}" in output
        assert "Chronos-2 (agent-tuned)" in output
