"""Prepare project data for the web dashboard (three-country edition).

Reads forecast_errors.parquet, search logs, configs, and ablation results
and writes JSON files that Observable Plot / OJS can consume directly.

Usage:
    uv run python webapp/_data/prepare_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
FE_PATH = RESULTS_DIR / "forecast_errors.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent

COUNTRIES = ["norway", "canada", "sweden"]
COUNTRY_DISPLAY = {"norway": "Norway", "canada": "Canada", "sweden": "Sweden"}
COUNTRY_TARGETS: dict[str, list[str]] = {
    "norway": ["cpi", "industrial_production", "retail_sales", "unemployment"],
    "canada": ["cpi", "industrial_production", "retail_sales", "unemployment"],
    "sweden": ["cpi", "industrial_production", "unemployment"],
}
HORIZONS = [1, 3, 6, 12]

METHOD_DISPLAY: dict[str, str] = {
    "random_walk": "Random Walk",
    "seasonal_naive": "Seasonal Naive",
    "ar": "AR(p)",
    "arima": "ARIMA",
    "ets": "ETS",
    "var": "VAR",
    "factor": "Factor Model",
    "bvar": "BVAR",
    "elastic_net": "Elastic Net",
    "zero_shot": "Chronos-2 (zero-shot)",
    "agent_tuned": "Chronos-2 (agent-tuned)",
    "manual_economist": "Chronos-2 (manual)",
}

METHOD_CATEGORY: dict[str, str] = {
    "random_walk": "naive",
    "seasonal_naive": "naive",
    "ar": "classical",
    "arima": "classical",
    "ets": "classical",
    "var": "multivariate",
    "factor": "multivariate",
    "bvar": "multivariate",
    "elastic_net": "ml",
    "zero_shot": "foundation",
    "agent_tuned": "foundation",
    "manual_economist": "foundation",
}

SUBPERIOD_BOUNDS: dict[str, tuple[str, str]] = {
    "pre_covid": ("2016-01-01", "2019-12-31"),
    "covid": ("2020-01-01", "2021-12-31"),
    "post_covid": ("2022-01-01", "2025-12-31"),
}

# Primary search state files per country
SEARCH_STATE_FILES: dict[str, str] = {
    "norway": "search_state_llm_42.json",
    "canada": "search_state_llm_42.json",
    "sweden": "search_state_llm_fixedgate_42.json",
}

SEARCH_LOG_FILES: dict[str, str] = {
    "norway": "search_log_llm_42.jsonl",
    "canada": "search_log_llm_42.jsonl",
    "sweden": "search_log_llm_fixedgate_42.jsonl",
}


def load_errors() -> pd.DataFrame:
    df = pd.read_parquet(FE_PATH)
    df["origin_date"] = pd.to_datetime(df["origin_date"])
    return df


def _compute_mase_series(
    method_df: pd.DataFrame, rw_df: pd.DataFrame, targets: list[str],
) -> dict[str, dict[int, float]]:
    """Compute MASE per target per horizon."""
    result: dict[str, dict[int, float]] = {}
    for target in targets:
        result[target] = {}
        for h in HORIZONS:
            m_sub = method_df[(method_df["target"] == target) & (method_df["horizon"] == h)]
            r_sub = rw_df[(rw_df["target"] == target) & (rw_df["horizon"] == h)]
            if m_sub.empty or r_sub.empty:
                continue
            shared = m_sub[["origin_date", "abs_error"]].merge(
                r_sub[["origin_date", "abs_error"]],
                on="origin_date", suffixes=("_m", "_rw"),
            )
            if shared.empty:
                continue
            rw_mae = shared["abs_error_rw"].mean()
            if rw_mae > 0:
                result[target][h] = float(shared["abs_error_m"].mean() / rw_mae)
    return result


def _compute_rmse_series(
    method_df: pd.DataFrame, targets: list[str],
) -> dict[str, dict[int, float]]:
    """Compute RMSE per target per horizon."""
    result: dict[str, dict[int, float]] = {}
    for target in targets:
        result[target] = {}
        for h in HORIZONS:
            sub = method_df[(method_df["target"] == target) & (method_df["horizon"] == h)]
            if sub.empty:
                continue
            result[target][h] = float(np.sqrt(sub["sq_error"].mean()))
    return result


def prepare_metrics(df: pd.DataFrame) -> None:
    """Generate per-country, per-era metrics for all methods."""
    records: list[dict] = []

    for country in COUNTRIES:
        targets = COUNTRY_TARGETS[country]
        for era in ["validation", "test"]:
            mask = df["country"] == country
            mask = mask & (df["is_validation"] if era == "validation" else df["is_test"])
            era_df = df[mask]

            rw = era_df[era_df["model_variant"] == "random_walk"]

            methods = era_df[["model_family", "model_variant"]].drop_duplicates()
            for _, row in methods.iterrows():
                family, variant = row["model_family"], row["model_variant"]
                method_df = era_df[
                    (era_df["model_family"] == family) & (era_df["model_variant"] == variant)
                ]

                mase_by_target = _compute_mase_series(method_df, rw, targets)
                rmse_by_target = _compute_rmse_series(method_df, targets)

                for target in targets:
                    for h in HORIZONS:
                        mase_val = mase_by_target.get(target, {}).get(h)
                        rmse_val = rmse_by_target.get(target, {}).get(h)
                        if mase_val is None and rmse_val is None:
                            continue
                        records.append({
                            "country": country,
                            "era": era,
                            "method": variant,
                            "display_name": METHOD_DISPLAY.get(variant, variant),
                            "family": family,
                            "category": METHOD_CATEGORY.get(variant, "other"),
                            "target": target,
                            "horizon": h,
                            "mase": round(mase_val, 4) if mase_val is not None else None,
                            "rmse": round(rmse_val, 4) if rmse_val is not None else None,
                        })

    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(records, indent=2))
    print(f"Wrote metrics.json ({len(records)} records)")


def prepare_subperiod_metrics(df: pd.DataFrame) -> None:
    """Generate subperiod test-era metrics."""
    test = df[df["is_test"]]
    records: list[dict] = []

    for country in COUNTRIES:
        targets = COUNTRY_TARGETS[country]
        c_test = test[test["country"] == country]
        c_rw = c_test[c_test["model_variant"] == "random_walk"]

        for sp_name, (sp_start, sp_end) in SUBPERIOD_BOUNDS.items():
            sp_data = c_test[
                (c_test["origin_date"] >= sp_start) & (c_test["origin_date"] <= sp_end)
            ]
            sp_rw = c_rw[
                (c_rw["origin_date"] >= sp_start) & (c_rw["origin_date"] <= sp_end)
            ]

            methods = sp_data[["model_family", "model_variant"]].drop_duplicates()
            for _, row in methods.iterrows():
                family, variant = row["model_family"], row["model_variant"]
                method_df = sp_data[
                    (sp_data["model_family"] == family) & (sp_data["model_variant"] == variant)
                ]

                mase_by_target = _compute_mase_series(method_df, sp_rw, targets)
                rmse_by_target = _compute_rmse_series(method_df, targets)

                for target in targets:
                    for h in HORIZONS:
                        mase_val = mase_by_target.get(target, {}).get(h)
                        rmse_val = rmse_by_target.get(target, {}).get(h)
                        if mase_val is None and rmse_val is None:
                            continue
                        records.append({
                            "country": country,
                            "subperiod": sp_name,
                            "method": variant,
                            "display_name": METHOD_DISPLAY.get(variant, variant),
                            "category": METHOD_CATEGORY.get(variant, "other"),
                            "target": target,
                            "horizon": h,
                            "mase": round(mase_val, 4) if mase_val is not None else None,
                            "rmse": round(rmse_val, 4) if rmse_val is not None else None,
                        })

    (OUTPUT_DIR / "subperiod_metrics.json").write_text(json.dumps(records, indent=2))
    print(f"Wrote subperiod_metrics.json ({len(records)} records)")


def prepare_gap_data(df: pd.DataFrame) -> None:
    """Generate validation-to-test gap data per country."""
    records: list[dict] = []

    for country in COUNTRIES:
        targets = COUNTRY_TARGETS[country]
        for family, variant, label in [
            ("chronos2", "zero_shot", "Zero-shot"),
            ("chronos2", "agent_tuned", "Agent-tuned"),
        ]:
            for era in ["validation", "test"]:
                mask = (df["country"] == country) & (df["model_family"] == family) & (df["model_variant"] == variant)
                mask = mask & (df["is_validation"] if era == "validation" else df["is_test"])
                era_df = df[mask]
                rw_mask = (df["country"] == country) & (df["model_variant"] == "random_walk")
                rw_mask = rw_mask & (df["is_validation"] if era == "validation" else df["is_test"])
                rw_df = df[rw_mask]

                mase_by_target = _compute_mase_series(era_df, rw_df, targets)
                # Average across targets and horizons
                all_vals = [v for t in mase_by_target.values() for v in t.values()]
                avg = float(np.mean(all_vals)) if all_vals else None

                h12_vals = [mase_by_target.get(t, {}).get(12) for t in targets]
                h12_vals = [v for v in h12_vals if v is not None]
                h12_avg = float(np.mean(h12_vals)) if h12_vals else None

                records.append({
                    "country": country,
                    "config": label,
                    "era": era,
                    "avg_mase": round(avg, 3) if avg is not None else None,
                    "h12_mase": round(h12_avg, 3) if h12_avg is not None else None,
                })

    (OUTPUT_DIR / "gap_data.json").write_text(json.dumps(records, indent=2))
    print(f"Wrote gap_data.json ({len(records)} records)")


def prepare_search_trajectories() -> None:
    """Load informed-LLM search trajectories per country."""
    all_data: dict[str, list] = {}

    for country in COUNTRIES:
        log_file = RESULTS_DIR / country / SEARCH_LOG_FILES[country]
        if not log_file.exists():
            all_data[country] = []
            continue
        iterations = []
        for line in log_file.read_text().strip().split("\n"):
            if line.strip():
                iterations.append(json.loads(line))
        all_data[country] = iterations

    (OUTPUT_DIR / "search_trajectories.json").write_text(json.dumps(all_data, indent=2))
    total = sum(len(v) for v in all_data.values())
    print(f"Wrote search_trajectories.json ({total} iterations across {len(COUNTRIES)} countries)")


def prepare_pipeline_configs() -> None:
    """Load best config per country from search state files."""
    configs: dict[str, dict] = {}

    for country in COUNTRIES:
        state_file = RESULTS_DIR / country / SEARCH_STATE_FILES[country]
        if not state_file.exists():
            continue
        state = json.loads(state_file.read_text())
        configs[country] = {
            "display_name": COUNTRY_DISPLAY[country],
            "best_score": state.get("best_score"),
            "best_config": state.get("best_config", {}),
            "iterations": state.get("iteration", 0),
        }

    (OUTPUT_DIR / "pipeline_configs.json").write_text(json.dumps(configs, indent=2))
    print(f"Wrote pipeline_configs.json ({len(configs)} countries)")


def prepare_ablation_data() -> None:
    """Load leave-one-out ablation results per country."""
    all_data: dict[str, dict] = {}

    for country in COUNTRIES:
        abl_path = RESULTS_DIR / country / "ablation_leave_one_out.json"
        if not abl_path.exists():
            continue
        abl = json.loads(abl_path.read_text())
        all_data[country] = {
            "display_name": COUNTRY_DISPLAY[country],
            "reference_score": abl.get("reference_score") or abl.get("best_score"),
            "ablations": abl.get("ablations", []),
        }

    (OUTPUT_DIR / "ablation_data.json").write_text(json.dumps(all_data, indent=2))
    print(f"Wrote ablation_data.json ({len(all_data)} countries)")


def prepare_search_comparison(df: pd.DataFrame) -> None:
    """Generate search method comparison data per country."""

    def _load_score(country: str, mode: str, seed: int, tag: str | None = None) -> float | None:
        suffix = f"{mode}_{tag}_{seed}" if tag else f"{mode}_{seed}"
        path = RESULTS_DIR / country / f"search_state_{suffix}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text()).get("best_score")

    def _avg_mase(country: str, family: str, variant: str, era: str) -> float | None:
        targets = COUNTRY_TARGETS[country]
        mask = (df["country"] == country) & (df["model_family"] == family) & (df["model_variant"] == variant)
        mask = mask & (df["is_validation"] if era == "validation" else df["is_test"])
        method_df = df[mask]
        rw_mask = (df["country"] == country) & (df["model_variant"] == "random_walk")
        rw_mask = rw_mask & (df["is_validation"] if era == "validation" else df["is_test"])
        rw_df = df[rw_mask]
        mase = _compute_mase_series(method_df, rw_df, targets)
        vals = [v for t in mase.values() for v in t.values()]
        return round(float(np.mean(vals)), 3) if vals else None

    search_methods = [
        ("Informed LLM", lambda c: _load_score(c, "llm", 42) if c != "sweden"
         else _load_score(c, "llm", 42, tag="fixedgate")),
        ("Blind LLM", lambda c: _load_score(c, "llm", 42, tag="blind") if c != "sweden"
         else _load_score(c, "llm", 42, tag="blind_fixedgate")),
        ("Random", lambda c: _load_score(c, "random", 42)),
        ("Greedy", lambda c: _load_score(c, "greedy", 0)),
        ("Manual economist", lambda c: _avg_mase(c, "chronos2", "manual_economist", "validation")),
        ("Zero-shot baseline", lambda c: _avg_mase(c, "chronos2", "zero_shot", "validation")),
    ]

    records: list[dict] = []
    for name, score_fn in search_methods:
        for country in COUNTRIES:
            score = score_fn(country)
            records.append({
                "method": name,
                "country": country,
                "display_country": COUNTRY_DISPLAY[country],
                "val_mase": score,
            })

    (OUTPUT_DIR / "search_comparison.json").write_text(json.dumps(records, indent=2))
    print(f"Wrote search_comparison.json ({len(records)} records)")


def main() -> None:
    print(f"Preparing data for web dashboard (three-country)...")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Output dir: {OUTPUT_DIR}")
    print()

    df = load_errors()
    print(f"  Loaded {len(df)} forecast error records\n")

    prepare_metrics(df)
    prepare_subperiod_metrics(df)
    prepare_gap_data(df)
    prepare_search_trajectories()
    prepare_pipeline_configs()
    prepare_ablation_data()
    prepare_search_comparison(df)

    print("\nDone.")


if __name__ == "__main__":
    main()
