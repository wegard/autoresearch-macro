"""Test that country metadata is complete.

Per REVISION-PLAN-4 §10.5: verify every country has complete metadata,
every series has a lag rule, and the common evaluation sample is documented.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = PROJECT_ROOT / "metadata"
CONFIGS_DIR = PROJECT_ROOT / "configs"

COUNTRIES = ["norway", "canada", "sweden"]
TARGETS = ["cpi", "industrial_production", "retail_sales", "unemployment"]

# Per-country dropped targets — variables that exist in the source country's
# data offering but cannot be used because of insufficient validation-era
# history. These should be present in the catalog with role != "target".
DROPPED_TARGETS = {
    "sweden": {"retail_sales"},  # SCB table only publishes from 2023-01
}


class TestPublicationLags:
    """Every country must have publication lags for all its variables."""

    def test_lags_file_exists(self) -> None:
        lag_file = CONFIGS_DIR / "publication_lags.yml"
        assert lag_file.exists(), "publication_lags.yml not found"

    def test_all_countries_have_lag_section(self) -> None:
        with open(CONFIGS_DIR / "publication_lags.yml") as f:
            lags = yaml.safe_load(f)
        for country in COUNTRIES:
            assert country in lags, f"Missing lag section for {country}"

    def test_all_targets_have_lags(self) -> None:
        with open(CONFIGS_DIR / "publication_lags.yml") as f:
            lags = yaml.safe_load(f)
        for country in COUNTRIES:
            country_lags = lags[country]
            for target in TARGETS:
                assert target in country_lags, (
                    f"Missing lag for {target} in {country}"
                )
                assert isinstance(country_lags[target], (int, float)), (
                    f"Lag for {target} in {country} is not numeric"
                )

    def test_global_series_have_lags(self) -> None:
        """Global series (FRED) should have lags at top level."""
        with open(CONFIGS_DIR / "publication_lags.yml") as f:
            lags = yaml.safe_load(f)
        global_series = ["brent_crude", "sp500", "fed_funds", "us_cpi", "vix", "global_epu"]
        for series in global_series:
            assert series in lags, f"Missing global lag for {series}"


class TestVariableCatalog:
    """The variable catalog must be complete."""

    def test_catalog_exists(self) -> None:
        path = METADATA_DIR / "variable_catalog.csv"
        assert path.exists(), "variable_catalog.csv not found"

    def test_catalog_has_all_countries(self) -> None:
        path = METADATA_DIR / "variable_catalog.csv"
        with open(path) as f:
            reader = csv.DictReader(f)
            countries_in_catalog = {row["country"] for row in reader}
        for country in COUNTRIES:
            assert country in countries_in_catalog, (
                f"Country {country} missing from variable_catalog.csv"
            )

    def test_catalog_has_all_targets_per_country(self) -> None:
        path = METADATA_DIR / "variable_catalog.csv"
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        for country in COUNTRIES:
            country_targets = {
                r["variable_name"] for r in rows
                if r["country"] == country and r["role"] == "target"
            }
            country_dropped = {
                r["variable_name"] for r in rows
                if r["country"] == country and r["role"] == "dropped"
            }
            expected_dropped = DROPPED_TARGETS.get(country, set())

            for target in TARGETS:
                if target in expected_dropped:
                    assert target in country_dropped, (
                        f"Target {target} should be marked role=dropped for "
                        f"{country} in variable_catalog.csv"
                    )
                else:
                    assert target in country_targets, (
                        f"Target {target} missing for {country} in variable_catalog.csv"
                    )


class TestCanadaTargetDecision:
    """Canada industrial output target decision must be documented."""

    def test_decision_file_exists(self) -> None:
        path = METADATA_DIR / "canada_target_decision.md"
        assert path.exists(), "canada_target_decision.md not found"

    def test_decision_mentions_monthly_gdp(self) -> None:
        path = METADATA_DIR / "canada_target_decision.md"
        text = path.read_text()
        assert "36-10-0434" in text or "36100434" in text, (
            "canada_target_decision.md should reference table 36-10-0434-01"
        )


class TestPartnerActivityMapping:
    """Partner activity mapping must exist and cover all countries."""

    def test_mapping_exists(self) -> None:
        path = METADATA_DIR / "partner_activity_mapping.csv"
        assert path.exists(), "partner_activity_mapping.csv not found"

    def test_mapping_covers_all_countries(self) -> None:
        path = METADATA_DIR / "partner_activity_mapping.csv"
        with open(path) as f:
            reader = csv.DictReader(f)
            countries_in_mapping = {row["country"] for row in reader}
        for country in COUNTRIES:
            assert country in countries_in_mapping, (
                f"Country {country} missing from partner_activity_mapping.csv"
            )
