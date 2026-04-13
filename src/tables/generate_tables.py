r"""Generate LaTeX table fragments from forecast_errors.parquet.

Produces .tex files in paper/tables/ for \input{} from main.tex.
Supports three-country (Norway, Canada, Sweden) stratification per
REVISION-PLAN-4.

Usage:
    uv run python src/tables/generate_tables.py
    uv run python src/tables/generate_tables.py --tables baseline gap
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
FE_PATH = RESULTS_DIR / "forecast_errors.parquet"
OUT_DIR = PROJECT_ROOT / "paper" / "tables"
METADATA_DIR = PROJECT_ROOT / "metadata"

HORIZONS = [1, 3, 6, 12]

COUNTRIES = ["norway", "canada", "sweden"]
COUNTRY_DISPLAY = {"norway": "Norway", "canada": "Canada", "sweden": "Sweden"}
COUNTRY_TARGETS: dict[str, list[str]] = {
    "norway": ["cpi", "industrial_production", "retail_sales", "unemployment"],
    "canada": ["cpi", "industrial_production", "retail_sales", "unemployment"],
    "sweden": ["cpi", "industrial_production", "unemployment"],
}

METHOD_DISPLAY: dict[tuple[str, str], str] = {
    ("classical", "random_walk"): "Random walk",
    ("classical", "seasonal_naive"): "Seasonal naive",
    ("classical", "ar"): "AR",
    ("classical", "arima"): "ARIMA",
    ("classical", "ets"): "ETS",
    ("classical", "var"): "VAR",
    ("classical", "factor"): "Factor model",
    ("classical", "bvar"): "BVAR",
    ("classical", "elastic_net"): "Elastic net",
    ("chronos2", "zero_shot"): "Chronos-2 (zero-shot)",
    ("chronos2", "agent_tuned"): "Chronos-2 (agent-tuned)",
    ("chronos2", "manual_economist"): "Chronos-2 (manual)",
}

TARGET_DISPLAY: dict[str, str] = {
    "cpi": "CPI",
    "industrial_production": "Industrial prod.",
    "retail_sales": "Retail sales",
    "unemployment": "Unemployment",
}

SUBPERIOD_BOUNDS: dict[str, tuple[str, str]] = {
    "Pre-COVID (2016--19)": ("2016-01-01", "2019-12-31"),
    "COVID (2020--21)": ("2020-01-01", "2021-12-31"),
    "Post-COVID (2022+)": ("2022-01-01", "2025-12-31"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_errors() -> pd.DataFrame:
    df = pd.read_parquet(FE_PATH)
    df["origin_date"] = pd.to_datetime(df["origin_date"])
    return df


def compute_mase(
    method_df: pd.DataFrame,
    rw_df: pd.DataFrame,
    targets: list[str] | None = None,
) -> pd.Series:
    """Compute avg MASE per horizon using shared origins between method and RW."""
    if targets is None:
        targets = sorted(method_df["target"].unique().tolist())

    mase_rows: list[dict] = []
    for target in targets:
        for h in HORIZONS:
            m_sub = method_df[(method_df["target"] == target) & (method_df["horizon"] == h)]
            r_sub = rw_df[(rw_df["target"] == target) & (rw_df["horizon"] == h)]
            if m_sub.empty or r_sub.empty:
                continue
            shared = m_sub[["origin_date", "abs_error"]].merge(
                r_sub[["origin_date", "abs_error"]],
                on="origin_date", suffixes=("_method", "_rw"),
            )
            if shared.empty:
                continue
            method_mae = shared["abs_error_method"].mean()
            rw_mae = shared["abs_error_rw"].mean()
            mase_rows.append({
                "target": target, "horizon": h,
                "mase": method_mae / rw_mae if rw_mae > 0 else float("nan"),
            })
    result = pd.DataFrame(mase_rows)
    if result.empty:
        return pd.Series(dtype=float)
    return result.groupby("horizon")["mase"].mean()


def _mase_for_method(
    df: pd.DataFrame, family: str, variant: str, country: str, era: str,
) -> dict[int, float]:
    """Convenience: compute per-horizon avg MASE for one method/country/era."""
    mask = df["country"] == country
    if era == "validation":
        mask = mask & df["is_validation"]
    else:
        mask = mask & df["is_test"]
    subset = df[mask & (df["model_family"] == family) & (df["model_variant"] == variant)]
    rw = df[mask & (df["model_variant"] == "random_walk")]
    if subset.empty or rw.empty:
        return {}
    mase = compute_mase(subset, rw, targets=COUNTRY_TARGETS[country])
    return {h: mase.get(h, float("nan")) for h in HORIZONS}


def _avg_mase(per_h: dict[int, float]) -> float:
    vals = [v for v in per_h.values() if not np.isnan(v)]
    return float(np.mean(vals)) if vals else float("nan")


def fmt(val: float, bold: bool = False) -> str:
    if np.isnan(val):
        return "---"
    s = f"{val:.3f}"
    return rf"\textbf{{{s}}}" if bold else s


def tex_escape(s: str) -> str:
    """Escape underscores and other LaTeX-special chars in table text."""
    return s.replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def _sweden_footnote() -> str:
    return (
        r"\footnotesize Sweden averages over 3 targets "
        r"(CPI, industrial production, unemployment); "
        r"retail sales excluded due to insufficient history."
    )


# ---------------------------------------------------------------------------
# Table 2: Baseline performance (test era, by country)
# ---------------------------------------------------------------------------


def generate_baseline_table(df: pd.DataFrame) -> str:
    """Test-era MASE by country and horizon for key methods."""
    method_order = [
        ("classical", "random_walk"),
        ("classical", "arima"),
        ("classical", "bvar"),
        ("classical", "elastic_net"),
        ("classical", "var"),
        ("classical", "factor"),
        ("chronos2", "zero_shot"),
        ("chronos2", "agent_tuned"),
        ("chronos2", "manual_economist"),
    ]

    lines = [
        r"\begin{tabular}{llcccc}",
        r"\toprule",
        r"Country & Method & $h{=}1$ & $h{=}3$ & $h{=}6$ & $h{=}12$ \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        results: dict[str, dict[int, float]] = {}
        for family, variant in method_order:
            per_h = _mase_for_method(df, family, variant, country, "test")
            if per_h:
                name = METHOD_DISPLAY.get((family, variant), variant)
                results[name] = per_h

        best_per_h: dict[int, float] = {}
        for h in HORIZONS:
            vals = [results[m][h] for m in results
                    if m != "Random walk" and h in results[m] and not np.isnan(results[m][h])]
            best_per_h[h] = min(vals) if vals else float("inf")

        for m_idx, (family, variant) in enumerate(method_order):
            name = METHOD_DISPLAY.get((family, variant), variant)
            if name not in results:
                continue
            prefix = rf"\multirow{{{len(results)}}}{{*}}{{{COUNTRY_DISPLAY[country]}}}" if m_idx == 0 else ""
            vals = " & ".join(
                fmt(results[name].get(h, float("nan")),
                    bold=(name != "Random walk" and abs(results[name].get(h, float("inf")) - best_per_h.get(h, float("inf"))) < 1e-4))
                for h in HORIZONS
            )
            lines.append(f"{prefix} & {name} & {vals} \\\\")

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Table 3: Search comparison
# ---------------------------------------------------------------------------


def _load_search_score(country: str, mode: str, seed: int, tag: str | None = None) -> float | None:
    """Load best validation MASE from a search state file."""
    suffix = f"{mode}_{tag}_{seed}" if tag else f"{mode}_{seed}"
    path = RESULTS_DIR / country / f"search_state_{suffix}.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    return d.get("best_score")


def generate_search_comparison_table(df: pd.DataFrame) -> str:
    """Search method comparison: informed vs blind vs random vs greedy vs manual."""
    search_methods = [
        ("Informed LLM", lambda c: _load_search_score(c, "llm", 42)
         if c != "sweden" else _load_search_score(c, "llm", 42, tag="fixedgate")),
        ("Blind LLM", lambda c: _load_search_score(c, "llm", 42, tag="blind")
         if c != "sweden" else _load_search_score(c, "llm", 42, tag="blind_fixedgate")),
        ("Random", lambda c: _load_search_score(c, "random", 42)),
        ("Greedy", lambda c: _load_search_score(c, "greedy", 0)),
        ("Manual economist", lambda c: _avg_mase(
            _mase_for_method(df, "chronos2", "manual_economist", c, "validation"))),
        ("Zero-shot baseline", lambda c: _avg_mase(
            _mase_for_method(df, "chronos2", "zero_shot", c, "validation"))),
    ]

    lines = [
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Search method & Norway & Canada & Sweden \\",
        r"\midrule",
    ]

    all_scores: dict[str, dict[str, float]] = {}
    for name, score_fn in search_methods:
        all_scores[name] = {}
        for country in COUNTRIES:
            s = score_fn(country)
            all_scores[name][country] = s if s is not None else float("nan")

    best_per_country: dict[str, float] = {}
    for country in COUNTRIES:
        vals = [all_scores[n][country] for n in all_scores
                if n != "Zero-shot baseline" and not np.isnan(all_scores[n][country])]
        best_per_country[country] = min(vals) if vals else float("inf")

    for name, _ in search_methods:
        cells = []
        for country in COUNTRIES:
            v = all_scores[name][country]
            is_best = (name != "Zero-shot baseline"
                       and not np.isnan(v)
                       and abs(v - best_per_country[country]) < 1e-4)
            cells.append(fmt(v, bold=is_best))
        lines.append(f"{name} & {' & '.join(cells)} \\\\")
        if name == "Zero-shot baseline":
            pass
        elif name == "Manual economist":
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Table 4: Selected pipelines
# ---------------------------------------------------------------------------


def generate_pipelines_table(df: pd.DataFrame) -> str:
    """Best search config per country: covariates, context, fine-tuning."""
    configs: dict[str, dict] = {}
    scores: dict[str, float] = {}
    state_files = {
        "norway": RESULTS_DIR / "norway/search_state_llm_42.json",
        "canada": RESULTS_DIR / "canada/search_state_llm_42.json",
        "sweden": RESULTS_DIR / "sweden/search_state_llm_fixedgate_42.json",
    }
    for country, path in state_files.items():
        if path.exists():
            d = json.loads(path.read_text())
            configs[country] = d["best_config"]
            scores[country] = d["best_score"]

    lines = [
        r"\begin{tabular}{lllclr}",
        r"\toprule",
        r"Country & Covariates & Transforms & Ctx & Fine-tune & Val.\ MASE \\",
        r"\midrule",
    ]

    for country in COUNTRIES:
        if country not in configs:
            continue
        cfg = configs[country]
        covs = tex_escape(", ".join(cfg.get("covariates", []))) or "---"
        transforms = cfg.get("transforms", {})
        if transforms:
            tx_parts = [f"{tex_escape(k)}: {tex_escape(v)}" for k, v in transforms.items()]
            tx_str = ", ".join(tx_parts)
        else:
            tx_str = "---"
        ctx = str(cfg.get("context_length")) if cfg.get("context_length") else "all"
        ft = "Yes" if cfg.get("fine_tune") else "No"
        if cfg.get("fine_tune"):
            ft += f" ({cfg.get('fine_tune_steps', '?')})"
        score = scores.get(country, float("nan"))
        lines.append(
            f"{COUNTRY_DISPLAY[country]} & {covs} & {tx_str} & {ctx} & {ft} & {fmt(score)} \\\\"
        )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Table 5: Validation-to-test gap
# ---------------------------------------------------------------------------


def generate_gap_table(df: pd.DataFrame) -> str:
    """Validation vs test MASE for zero-shot and agent-tuned, by country."""
    methods = [
        ("chronos2", "zero_shot", "Zero-shot"),
        ("chronos2", "agent_tuned", "Agent-tuned"),
    ]

    lines = [
        r"\begin{tabular}{llcccc}",
        r"\toprule",
        r"Country & Config & Val & Test & Gap (\%) & $h{=}12$ Test \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        for m_idx, (family, variant, label) in enumerate(methods):
            val_h = _mase_for_method(df, family, variant, country, "validation")
            test_h = _mase_for_method(df, family, variant, country, "test")
            val_avg = _avg_mase(val_h)
            test_avg = _avg_mase(test_h)

            if not np.isnan(val_avg) and not np.isnan(test_avg) and val_avg > 0:
                gap = (test_avg - val_avg) / val_avg * 100
                gap_str = f"{gap:+.1f}\\%"
            else:
                gap_str = "---"

            h12_test = test_h.get(12, float("nan"))

            prefix = rf"\multirow{{2}}{{*}}{{{COUNTRY_DISPLAY[country]}}}" if m_idx == 0 else ""
            lines.append(
                f"{prefix} & {label} & {fmt(val_avg)} & {fmt(test_avg)} "
                f"& {gap_str} & {fmt(h12_test)} \\\\"
            )

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Table 6: Ablation (leave-one-out)
# ---------------------------------------------------------------------------


def generate_ablation_table(df: pd.DataFrame) -> str:
    """Leave-one-out ablation summary per country."""
    lines = [
        r"\begin{tabular}{llrr}",
        r"\toprule",
        r"Country & Component removed & MASE & Degrad.\ (\%) \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        abl_path = RESULTS_DIR / country / "ablation_leave_one_out.json"
        if not abl_path.exists():
            continue
        abl = json.loads(abl_path.read_text())
        ref = abl.get("reference_score") or abl.get("best_score", float("nan"))

        lines.append(
            rf"\multirow{{{1 + len(abl['ablations'])}}}{{*}}"
            rf"{{{COUNTRY_DISPLAY[country]}}} & Full config & {fmt(ref)} & --- \\"
        )

        for entry in abl["ablations"]:
            name = tex_escape(entry["name"].replace("drop_", "").replace("_", " "))
            score = entry.get("score", float("nan"))
            deg = entry.get("degradation_pct")
            deg_str = f"{deg:+.2f}\\%" if deg is not None else "---"
            lines.append(f" & $-$ {name} & {fmt(score)} & {deg_str} \\\\")

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Auto-generated macros for prose numbers
# ---------------------------------------------------------------------------


def generate_macros(df: pd.DataFrame) -> str:
    r"""Generate \newcommand definitions for key numbers used in prose."""
    cmds: list[str] = []

    def add(name: str, value: float | int | str) -> None:
        if isinstance(value, float):
            if np.isnan(value):
                cmds.append(rf"\newcommand{{\{name}}}{{---}}")
            else:
                cmds.append(rf"\newcommand{{\{name}}}{{{value:.3f}}}")
        elif isinstance(value, int):
            cmds.append(rf"\newcommand{{\{name}}}{{{value}}}")
        else:
            cmds.append(rf"\newcommand{{\{name}}}{{{value}}}")

    for country in COUNTRIES:
        c = country[:3]  # nor, can, swe

        # Zero-shot validation and test MASE
        zs_val = _mase_for_method(df, "chronos2", "zero_shot", country, "validation")
        zs_test = _mase_for_method(df, "chronos2", "zero_shot", country, "test")
        add(f"{c}ZsVal", _avg_mase(zs_val))
        add(f"{c}ZsTest", _avg_mase(zs_test))

        # Agent-tuned validation and test
        at_val = _mase_for_method(df, "chronos2", "agent_tuned", country, "validation")
        at_test = _mase_for_method(df, "chronos2", "agent_tuned", country, "test")
        add(f"{c}AtVal", _avg_mase(at_val))
        add(f"{c}AtTest", _avg_mase(at_test))

        # Validation improvement %
        zs_v = _avg_mase(zs_val)
        at_v = _avg_mase(at_val)
        if not np.isnan(zs_v) and not np.isnan(at_v) and zs_v > 0:
            add(f"{c}ValGainPct", f"{(1 - at_v / zs_v) * 100:.1f}\\%")

        # Test gap %
        if not np.isnan(at_v) and not np.isnan(_avg_mase(at_test)) and at_v > 0:
            gap = (_avg_mase(at_test) - at_v) / at_v * 100
            add(f"{c}TestGapPct", f"{gap:+.1f}\\%")

        # Best search score from state file
        state_files = {
            "norway": RESULTS_DIR / "norway/search_state_llm_42.json",
            "canada": RESULTS_DIR / "canada/search_state_llm_42.json",
            "sweden": RESULTS_DIR / "sweden/search_state_llm_fixedgate_42.json",
        }
        sf = state_files.get(country)
        if sf and sf.exists():
            d = json.loads(sf.read_text())
            add(f"{c}SearchBest", d["best_score"])

        # ARIMA test
        arima_test = _mase_for_method(df, "classical", "arima", country, "test")
        add(f"{c}ArimaTest", _avg_mase(arima_test))

        # RW test (should be 1.000)
        rw_test = _mase_for_method(df, "classical", "random_walk", country, "test")
        add(f"{c}RwTest", _avg_mase(rw_test))

        # Number of targets
        add(f"{c}Ntargets", len(COUNTRY_TARGETS[country]))

    # Global counts
    n_val = df[df["is_validation"]]["origin_date"].nunique()
    n_test = df[df["is_test"]]["origin_date"].nunique()
    add("nValOrigins", n_val)
    add("nTestOrigins", n_test)
    add("nCountries", len(COUNTRIES))

    return "% Auto-generated by src/tables/generate_tables.py\n" + "\n".join(cmds) + "\n"


# ---------------------------------------------------------------------------
# Legacy tables (updated for country dimension)
# ---------------------------------------------------------------------------


def generate_validation_table(df: pd.DataFrame) -> str:
    """Validation era avg MASE by method, country-stratified."""
    method_order = [
        ("classical", "random_walk"),
        ("classical", "arima"),
        ("classical", "bvar"),
        ("classical", "var"),
        ("classical", "factor"),
        ("chronos2", "zero_shot"),
    ]

    lines = [
        r"\begin{tabular}{llcccc}",
        r"\toprule",
        r"Country & Method & $h{=}1$ & $h{=}3$ & $h{=}6$ & $h{=}12$ \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        results: dict[str, dict[int, float]] = {}
        for family, variant in method_order:
            per_h = _mase_for_method(df, family, variant, country, "validation")
            if per_h:
                name = METHOD_DISPLAY.get((family, variant), variant)
                results[name] = per_h

        best_per_h: dict[int, float] = {}
        for h in HORIZONS:
            vals = [results[m][h] for m in results
                    if m != "Random walk" and h in results[m] and not np.isnan(results[m][h])]
            best_per_h[h] = min(vals) if vals else float("inf")

        n_shown = len(results)
        for m_idx, (family, variant) in enumerate(method_order):
            name = METHOD_DISPLAY.get((family, variant), variant)
            if name not in results:
                continue
            prefix = rf"\multirow{{{n_shown}}}{{*}}{{{COUNTRY_DISPLAY[country]}}}" if m_idx == 0 else ""
            vals = " & ".join(
                fmt(results[name].get(h, float("nan")),
                    bold=(name != "Random walk"
                          and abs(results[name].get(h, float("inf")) - best_per_h.get(h, float("inf"))) < 1e-4))
                for h in HORIZONS
            )
            lines.append(f"{prefix} & {name} & {vals} \\\\")

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def generate_test_table(df: pd.DataFrame) -> str:
    """Test era avg MASE by method, country-stratified."""
    method_order = [
        ("classical", "random_walk"),
        ("classical", "arima"),
        ("classical", "bvar"),
        ("classical", "var"),
        ("classical", "factor"),
        ("chronos2", "zero_shot"),
        ("chronos2", "agent_tuned"),
    ]

    lines = [
        r"\begin{tabular}{llcccc}",
        r"\toprule",
        r"Country & Method & $h{=}1$ & $h{=}3$ & $h{=}6$ & $h{=}12$ \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        results: dict[str, dict[int, float]] = {}
        for family, variant in method_order:
            per_h = _mase_for_method(df, family, variant, country, "test")
            if per_h:
                name = METHOD_DISPLAY.get((family, variant), variant)
                results[name] = per_h

        best_per_h: dict[int, float] = {}
        for h in HORIZONS:
            vals = [results[m][h] for m in results
                    if m != "Random walk" and h in results[m] and not np.isnan(results[m][h])]
            best_per_h[h] = min(vals) if vals else float("inf")

        n_shown = len(results)
        for m_idx, (family, variant) in enumerate(method_order):
            name = METHOD_DISPLAY.get((family, variant), variant)
            if name not in results:
                continue
            prefix = rf"\multirow{{{n_shown}}}{{*}}{{{COUNTRY_DISPLAY[country]}}}" if m_idx == 0 else ""
            vals = " & ".join(
                fmt(results[name].get(h, float("nan")),
                    bold=(name != "Random walk"
                          and abs(results[name].get(h, float("inf")) - best_per_h.get(h, float("inf"))) < 1e-4))
                for h in HORIZONS
            )
            lines.append(f"{prefix} & {name} & {vals} \\\\")

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def generate_subperiod_table(df: pd.DataFrame) -> str:
    """Subperiod avg RMSE across targets, country-stratified."""
    test = df[df["is_test"]]
    methods_to_show = [
        (("classical", "random_walk"), "RW"),
        (("classical", "arima"), "ARIMA"),
        (("chronos2", "zero_shot"), "C2-ZS"),
        (("chronos2", "agent_tuned"), "C2-AT"),
    ]

    lines = [
        r"\small",
        r"\begin{tabular}{lllcccc}",
        r"\toprule",
        r"Country & Subperiod & Method & $h{=}1$ & $h{=}3$ & $h{=}6$ & $h{=}12$ \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        c_test = test[test["country"] == country]
        targets = COUNTRY_TARGETS[country]

        for sp_idx, (sp_name, (sp_start, sp_end)) in enumerate(SUBPERIOD_BOUNDS.items()):
            sp_data = c_test[(c_test["origin_date"] >= sp_start) & (c_test["origin_date"] <= sp_end)]

            best_per_h: dict[int, float] = {h: float("inf") for h in HORIZONS}
            sp_results: dict[str, dict[int, float]] = {}

            for (family, variant), display_name in methods_to_show:
                subset = sp_data[(sp_data["model_family"] == family) & (sp_data["model_variant"] == variant)]
                if subset.empty:
                    continue
                rmse_per_h: dict[int, float] = {}
                for h in HORIZONS:
                    h_data = subset[subset["horizon"] == h]
                    if h_data.empty:
                        continue
                    rmse_per_target = []
                    for t in targets:
                        t_data = h_data[h_data["target"] == t]
                        if not t_data.empty:
                            rmse_per_target.append(np.sqrt(t_data["sq_error"].mean()))
                    if rmse_per_target:
                        rmse_per_h[h] = float(np.mean(rmse_per_target))
                        best_per_h[h] = min(best_per_h[h], rmse_per_h[h])
                sp_results[display_name] = rmse_per_h

            for m_idx, ((family, variant), display_name) in enumerate(methods_to_show):
                if display_name not in sp_results:
                    continue
                c_prefix = rf"\multirow{{{len(SUBPERIOD_BOUNDS) * len(methods_to_show)}}}{{*}}{{{COUNTRY_DISPLAY[country]}}}" if sp_idx == 0 and m_idx == 0 else ""
                sp_prefix = rf"\multirow{{{len(methods_to_show)}}}{{*}}{{{sp_name}}}" if m_idx == 0 else ""
                vals = " & ".join(
                    fmt(sp_results[display_name].get(h, float("nan")),
                        bold=(abs(sp_results[display_name].get(h, float("inf")) - best_per_h[h]) < 0.001))
                    for h in HORIZONS
                )
                lines.append(f"{c_prefix} & {sp_prefix} & {display_name} & {vals} \\\\")

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def generate_per_variable_test_table(df: pd.DataFrame) -> str:
    """Per-variable MASE, test era, country-stratified."""
    test = df[df["is_test"]]

    methods = [
        (("classical", "random_walk"), "RW"),
        (("classical", "arima"), "ARIMA"),
        (("classical", "bvar"), "BVAR"),
        (("chronos2", "zero_shot"), "C2-ZS"),
        (("chronos2", "agent_tuned"), "C2-AT"),
    ]
    method_short_names = [m[1] for m in methods]

    lines = [
        r"\small",
        r"\begin{tabular}{lllccccc}",
        r"\toprule",
        r"Country & Variable & $h$ & RW & ARIMA & BVAR & C2-ZS & C2-AT \\",
        r"\midrule",
    ]

    for c_idx, country in enumerate(COUNTRIES):
        c_test = test[test["country"] == country]
        c_rw = c_test[c_test["model_variant"] == "random_walk"]
        targets = COUNTRY_TARGETS[country]

        mase_data: dict[str, dict[str, dict[int, float]]] = {}
        for t in targets:
            mase_data[t] = {}
            for (family, variant), short_name in methods:
                mase_data[t][short_name] = {}
                subset = c_test[(c_test["model_family"] == family)
                                & (c_test["model_variant"] == variant)
                                & (c_test["target"] == t)]
                rw_subset = c_rw[c_rw["target"] == t]
                for h in HORIZONS:
                    h_sub = subset[subset["horizon"] == h]
                    rw_h = rw_subset[rw_subset["horizon"] == h]
                    if h_sub.empty or rw_h.empty:
                        continue
                    shared = h_sub[["origin_date", "abs_error"]].merge(
                        rw_h[["origin_date", "abs_error"]],
                        on="origin_date", suffixes=("_method", "_rw"),
                    )
                    if shared.empty:
                        continue
                    method_mae = shared["abs_error_method"].mean()
                    rw_mae = shared["abs_error_rw"].mean()
                    mase_data[t][short_name][h] = method_mae / rw_mae if rw_mae > 0 else float("nan")

        for t_idx, t in enumerate(targets):
            display = TARGET_DISPLAY.get(t, t)
            for h_idx, h in enumerate(HORIZONS):
                row_vals = {sn: mase_data[t].get(sn, {}).get(h, float("nan")) for sn in method_short_names}
                non_rw = [v for k, v in row_vals.items() if k != "RW" and not np.isnan(v)]
                best = min(non_rw) if non_rw else float("inf")

                c_prefix = (rf"\multirow{{{len(targets) * len(HORIZONS)}}}{{*}}"
                            rf"{{{COUNTRY_DISPLAY[country]}}}" if t_idx == 0 and h_idx == 0 else "")
                t_prefix = rf"\multirow{{{len(HORIZONS)}}}{{*}}{{{display}}}" if h_idx == 0 else ""
                cells = [fmt(row_vals.get(sn, float("nan")),
                             bold=(abs(row_vals.get(sn, float("inf")) - best) < 0.001 and sn != "RW"))
                         for sn in method_short_names]
                lines.append(f"{c_prefix} & {t_prefix} & {h} & {' & '.join(cells)} \\\\")

        if c_idx < len(COUNTRIES) - 1:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TABLE_GENERATORS: dict[str, tuple[str, callable]] = {
    "validation": ("tab_validation.tex", generate_validation_table),
    "test": ("tab_test.tex", generate_test_table),
    "baseline": ("tab_baseline.tex", generate_baseline_table),
    "search_comparison": ("tab_search_comparison.tex", generate_search_comparison_table),
    "pipelines": ("tab_pipelines.tex", generate_pipelines_table),
    "gap": ("tab_gap.tex", generate_gap_table),
    "ablation": ("tab_ablation.tex", generate_ablation_table),
    "subperiods": ("tab_subperiods.tex", generate_subperiod_table),
    "per_variable_test": ("tab_per_variable_test.tex", generate_per_variable_test_table),
    "macros": ("auto_macros.tex", generate_macros),
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Generate LaTeX tables")
    parser.add_argument("--tables", nargs="*", default=list(TABLE_GENERATORS.keys()),
                        help="Which tables to generate")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_errors()

    for table_name in args.tables:
        if table_name not in TABLE_GENERATORS:
            logger.warning("Unknown table: %s", table_name)
            continue
        filename, generator = TABLE_GENERATORS[table_name]
        content = generator(df)
        out_path = OUT_DIR / filename
        out_path.write_text(content)
        logger.info("Wrote %s", out_path)


if __name__ == "__main__":
    main()
