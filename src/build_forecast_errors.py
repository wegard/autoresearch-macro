"""Build a consolidated forecast_errors.parquet from per-method result files.

Reads point_forecasts.parquet from each results/{era}/{method}/ directory,
joins against the macro panel for actuals, and produces a single long-format
parquet file — the single source of truth for all tables and figures.

Usage:
    uv run python src/build_forecast_errors.py
    uv run python src/build_forecast_errors.py --validate
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
PANEL_PATH = PROJECT_ROOT / "data" / "processed" / "macro_panel.parquet"
OUTPUT_PATH = RESULTS_DIR / "forecast_errors.parquet"

TARGETS = ["cpi", "industrial_production", "retail_sales", "unemployment"]
HORIZONS = [1, 3, 6, 12]

# Method classification
METHOD_FAMILIES: dict[str, tuple[str, str, str]] = {
    # method_dir: (model_family, model_variant, search_method)
    "random_walk":   ("classical", "random_walk",   "none"),
    "seasonal_naive": ("classical", "seasonal_naive", "none"),
    "ar":            ("classical", "ar",            "none"),
    "arima":         ("classical", "arima",         "none"),
    "ets":           ("classical", "ets",           "none"),
    "var":           ("classical", "var",           "none"),
    "factor":        ("classical", "factor",        "none"),
    "bvar":          ("classical", "bvar",          "none"),
    "elastic_net":   ("classical", "elastic_net",   "none"),
    "chronos2_zs":   ("chronos2",  "zero_shot",     "none"),
    "chronos2_ft":   ("chronos2",  "agent_tuned",   "llm_informed"),
    "chronos2_manual": ("chronos2", "manual_economist", "manual"),
}

# Test-era subperiod boundaries
TEST_SUBPERIODS: dict[str, tuple[str, str]] = {
    "pre_covid":  ("2016-01-31", "2019-12-31"),
    "covid":      ("2020-01-31", "2021-12-31"),
    "post_covid": ("2022-01-31", "2025-12-31"),
}


def load_panel() -> pd.DataFrame:
    """Load the macro panel with datetime index."""
    panel = pd.read_parquet(PANEL_PATH)
    # Ensure datetime index
    if not isinstance(panel.index, pd.DatetimeIndex):
        panel.index = pd.to_datetime(panel.index)
    return panel


def get_actual(panel: pd.DataFrame, origin_date: pd.Timestamp,
               variable: str, horizon: int) -> float | None:
    """Look up the actual value h months ahead of the origin date."""
    target_date = origin_date + pd.DateOffset(months=horizon)
    target_date = target_date + pd.offsets.MonthEnd(0)
    if target_date in panel.index and variable in panel.columns:
        val = panel.loc[target_date, variable]
        if pd.notna(val):
            return float(val)
    return None


def get_rw_forecast(panel: pd.DataFrame, origin_date: pd.Timestamp,
                    variable: str, pub_lag_days: int) -> float | None:
    """Get the random walk forecast (last available observation at origin)."""
    from datetime import timedelta
    cutoff = origin_date - timedelta(days=pub_lag_days)
    available = panel.loc[:cutoff, variable].dropna()
    if not available.empty:
        return float(available.iloc[-1])
    return None


def process_method(
    era: str,
    method_dir: str,
    panel: pd.DataFrame,
    pub_lags: dict[str, int],
    result_base: Path | None = None,
    country: str = "norway",
) -> pd.DataFrame:
    """Process one method's point_forecasts.parquet into long-format errors."""
    if result_base is None:
        result_base = RESULTS_DIR
    pf_path = result_base / era / method_dir / "point_forecasts.parquet"
    if not pf_path.exists():
        logger.warning("Missing: %s", pf_path)
        return pd.DataFrame()

    pf = pd.read_parquet(pf_path)

    # Ensure index is datetime
    if not isinstance(pf.index, pd.DatetimeIndex):
        pf.index = pd.to_datetime(pf.index)

    family, variant, search = METHOD_FAMILIES.get(
        method_dir, ("unknown", method_dir, "none")
    )

    rows: list[dict] = []
    for origin_date in pf.index:
        origin_ts = pd.Timestamp(origin_date)
        for target in TARGETS:
            for h in HORIZONS:
                col = f"{target}_h{h}"
                if col not in pf.columns:
                    continue
                y_pred = pf.loc[origin_date, col]
                if pd.isna(y_pred):
                    continue
                y_true = get_actual(panel, origin_ts, target, h)
                if y_true is None:
                    continue

                abs_err = abs(y_true - float(y_pred))
                sq_err = (y_true - float(y_pred)) ** 2

                rows.append({
                    "country": country,
                    "target": target,
                    "origin_date": origin_ts,
                    "horizon": h,
                    "model_family": family,
                    "model_variant": variant,
                    "search_method": search,
                    "seed": 0,
                    "run_id": f"{method_dir}_{era}",
                    "y_true": y_true,
                    "y_pred": float(y_pred),
                    "abs_error": abs_err,
                    "sq_error": sq_err,
                    "is_validation": era == "validation",
                    "is_test": era == "test",
                })

    return pd.DataFrame(rows)


def load_publication_lags() -> dict[str, int]:
    """Load publication lags from configs."""
    import yaml
    lag_path = PROJECT_ROOT / "configs" / "publication_lags.yml"
    with open(lag_path) as f:
        return yaml.safe_load(f)


def _load_country_panel(country: str) -> pd.DataFrame:
    """Load the macro panel for a specific country."""
    if country == "norway":
        return load_panel()
    elif country == "sweden":
        panel_path = PROJECT_ROOT / "data" / "processed" / "sweden" / "macro_panel.parquet"
        panel = pd.read_parquet(panel_path)
        if not isinstance(panel.index, pd.DatetimeIndex):
            panel.index = pd.to_datetime(panel.index)
        return panel
    elif country == "canada":
        panel_path = PROJECT_ROOT / "data" / "processed" / "canada" / "macro_panel.parquet"
        panel = pd.read_parquet(panel_path)
        if not isinstance(panel.index, pd.DatetimeIndex):
            panel.index = pd.to_datetime(panel.index)
        return panel
    raise ValueError(f"Unknown country: {country}")


def _scan_results_dir(country: str) -> list[tuple[str, str, str]]:
    """Find all (country, era, method) result dirs.

    Returns list of (country, era, method_dir_name) tuples.
    """
    found: list[tuple[str, str, str]] = []
    if country == "norway":
        # Norway: flat structure results/{era}/{method}
        for era in ["validation", "test"]:
            era_dir = RESULTS_DIR / era
            if not era_dir.exists():
                continue
            for method_dir in sorted(era_dir.iterdir()):
                if method_dir.is_dir() and method_dir.name in METHOD_FAMILIES:
                    found.append(("norway", era, method_dir.name))
    # Country structure: results/{country}/{era}/{method}
    country_dir = RESULTS_DIR / country
    if country_dir.exists():
        for era in ["validation", "test"]:
            era_dir = country_dir / era
            if not era_dir.exists():
                continue
            for method_dir in sorted(era_dir.iterdir()):
                if method_dir.is_dir() and method_dir.name in METHOD_FAMILIES:
                    found.append((country, era, method_dir.name))
    return found


def build_forecast_errors() -> pd.DataFrame:
    """Build the complete forecast_errors DataFrame for all countries."""
    all_frames: list[pd.DataFrame] = []

    for country in ["norway", "canada", "sweden"]:
        # Try to load panel for this country
        try:
            panel = _load_country_panel(country)
        except (FileNotFoundError, ValueError):
            logger.info("No panel found for %s, skipping", country)
            continue

        pub_lags = load_publication_lags()
        entries = _scan_results_dir(country)
        if not entries:
            continue

        for c, era, method_name in entries:
            # Determine the base path for this result
            if c == "norway" and (RESULTS_DIR / era / method_name).exists():
                result_base = RESULTS_DIR
            else:
                result_base = RESULTS_DIR / c

            pf_path = result_base / era / method_name / "point_forecasts.parquet"
            if not pf_path.exists():
                continue

            logger.info("Processing %s/%s/%s", c, era, method_name)
            df = process_method(
                era, method_name, panel, pub_lags,
                result_base=result_base, country=c,
            )
            if not df.empty:
                all_frames.append(df)

    if not all_frames:
        raise RuntimeError("No forecast data found")

    result = pd.concat(all_frames, ignore_index=True)

    # Set dtypes
    result["origin_date"] = pd.to_datetime(result["origin_date"])
    result["horizon"] = result["horizon"].astype(int)
    result["is_validation"] = result["is_validation"].astype(bool)
    result["is_test"] = result["is_test"].astype(bool)

    return result


def validate_against_metrics(df: pd.DataFrame) -> list[str]:
    """Validate forecast_errors against stored metrics.json files."""
    issues: list[str] = []

    # Scan all country directories + flat structure
    scan_targets: list[tuple[str, Path]] = [
        ("norway", RESULTS_DIR),  # flat: results/{era}/{method}
    ]
    for country in ["canada", "sweden"]:
        country_dir = RESULTS_DIR / country
        if country_dir.exists():
            scan_targets.append((country, country_dir))

    for country, base_dir in scan_targets:
        for era in ["validation", "test"]:
            era_dir = base_dir / era
            if not era_dir.exists():
                continue
            for method_dir in sorted(era_dir.iterdir()):
                if not method_dir.is_dir():
                    continue
                method_name = method_dir.name
                if method_name not in METHOD_FAMILIES:
                    continue
                metrics_path = method_dir / "metrics.json"
                if not metrics_path.exists():
                    continue

                with open(metrics_path) as f:
                    stored = json.load(f)

                family, variant, _ = METHOD_FAMILIES[method_name]
                is_val = era == "validation"

                for target in TARGETS:
                    if target not in stored["metrics"]:
                        continue
                    for h_str, m in stored["metrics"][target].items():
                        h = int(h_str)
                        mask = (
                            (df["country"] == country)
                            & (df["target"] == target)
                            & (df["horizon"] == h)
                            & (df["model_family"] == family)
                            & (df["model_variant"] == variant)
                            & (df["is_validation"] == is_val)
                        )
                        subset = df[mask]

                        # Check origin count
                        if len(subset) != m["n_origins"]:
                            issues.append(
                                f"{country}/{era}/{method_name} {target} h={h}: "
                                f"n_origins {len(subset)} vs stored {m['n_origins']}"
                            )

                        # Check MAE
                        if len(subset) > 0:
                            computed_mae = float(subset["abs_error"].mean())
                            stored_mae = m["mae"]
                            if abs(computed_mae - stored_mae) > 0.01:
                                issues.append(
                                    f"{country}/{era}/{method_name} {target} h={h}: "
                                    f"MAE {computed_mae:.6f} vs stored {stored_mae:.6f}"
                                )

    return issues


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Build forecast_errors.parquet")
    parser.add_argument("--validate", action="store_true",
                        help="Validate against stored metrics.json files")
    args = parser.parse_args()

    df = build_forecast_errors()
    df.to_parquet(OUTPUT_PATH, index=False)

    # Summary
    n_methods = df.groupby(["model_family", "model_variant"]).ngroups
    n_origins_val = df[df["is_validation"]]["origin_date"].nunique()
    n_origins_test = df[df["is_test"]]["origin_date"].nunique()
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  Rows: {len(df):,}")
    print(f"  Methods: {n_methods}")
    print(f"  Validation origins: {n_origins_val}")
    print(f"  Test origins: {n_origins_test}")
    print(f"  Countries: {df['country'].unique().tolist()}")
    print(f"  Targets: {df['target'].unique().tolist()}")
    print(f"  Horizons: {sorted(df['horizon'].unique().tolist())}")

    if args.validate:
        print("\nValidating against stored metrics...")
        issues = validate_against_metrics(df)
        if issues:
            print(f"\n{len(issues)} validation issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("All validations passed.")


if __name__ == "__main__":
    main()
