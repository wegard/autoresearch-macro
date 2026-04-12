"""Generate all paper figures (three-country version).

Produces PDF figures in paper/figures/ for inclusion in main.tex.

Usage:
    uv run python scripts/generate_figures.py
    uv run python scripts/generate_figures.py --figures search_trajectory ablation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "paper" / "figures"
RESULTS_DIR = PROJECT_ROOT / "results"
FE_PATH = RESULTS_DIR / "forecast_errors.parquet"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

COUNTRIES = ["norway", "canada", "sweden"]
COUNTRY_DISPLAY = {"norway": "Norway", "canada": "Canada", "sweden": "Sweden"}
COUNTRY_COLORS = {"norway": "#2c3e50", "canada": "#c0392b", "sweden": "#2980b9"}
COUNTRY_TARGETS = {
    "norway": ["cpi", "industrial_production", "retail_sales", "unemployment"],
    "canada": ["cpi", "industrial_production", "retail_sales", "unemployment"],
    "sweden": ["cpi", "industrial_production", "unemployment"],
}

HORIZONS = [1, 3, 6, 12]

SEARCH_LOG_FILES = {
    "norway": RESULTS_DIR / "norway" / "search_log_llm_42.jsonl",
    "canada": RESULTS_DIR / "canada" / "search_log_llm_42.jsonl",
    "sweden": RESULTS_DIR / "sweden" / "search_log_llm_fixedgate_42.jsonl",
}

SUBPERIOD_BOUNDS = {
    "Pre-COVID\n(2016--19)": ("2016-01-01", "2019-12-31"),
    "COVID\n(2020--21)": ("2020-01-01", "2021-12-31"),
    "Post-COVID\n(2022+)": ("2022-01-01", "2025-12-31"),
}


def _load_search_log(country: str) -> list[dict]:
    """Load the informed LLM search log for a country (last run only)."""
    path = SEARCH_LOG_FILES[country]
    if not path.exists():
        return []
    all_iters = []
    for line in path.read_text().strip().split("\n"):
        if line.strip():
            all_iters.append(json.loads(line))
    # Find the last run's baseline (last occurrence of iteration 0)
    last_run_start = 0
    for i, r in enumerate(all_iters):
        if r["iteration"] == 0:
            last_run_start = i
    return all_iters[last_run_start:]


def _compute_mase_per_method_country(
    df: pd.DataFrame, country: str, era: str,
) -> dict[str, float]:
    """Compute avg MASE (across targets and horizons) for each method variant."""
    targets = COUNTRY_TARGETS[country]
    mask = df["country"] == country
    if era == "validation":
        mask = mask & df["is_validation"]
    else:
        mask = mask & df["is_test"]
    era_df = df[mask]
    rw = era_df[era_df["model_variant"] == "random_walk"]

    results: dict[str, float] = {}
    for variant in era_df["model_variant"].unique():
        subset = era_df[era_df["model_variant"] == variant]
        mase_vals = []
        for t in targets:
            for h in HORIZONS:
                m_sub = subset[(subset["target"] == t) & (subset["horizon"] == h)]
                r_sub = rw[(rw["target"] == t) & (rw["horizon"] == h)]
                if m_sub.empty or r_sub.empty:
                    continue
                shared = m_sub[["origin_date", "abs_error"]].merge(
                    r_sub[["origin_date", "abs_error"]],
                    on="origin_date", suffixes=("_m", "_rw"),
                )
                if shared.empty:
                    continue
                mase = shared["abs_error_m"].mean() / shared["abs_error_rw"].mean()
                mase_vals.append(mase)
        if mase_vals:
            results[variant] = float(np.mean(mase_vals))
    return results


# ---------------------------------------------------------------------------
# Figure 1: Search trajectory by country (1x3 subplots)
# ---------------------------------------------------------------------------


def fig_search_trajectory():
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True)

    for ax, country in zip(axes, COUNTRIES):
        iters = _load_search_log(country)
        if not iters:
            ax.set_title(COUNTRY_DISPLAY[country])
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue

        color_map = {
            "accepted": "#2ecc71", "rejected": "#e74c3c", "error": "#f39c12",
        }

        for r in iters:
            score = r.get("full_score") or r.get("quick_score")
            if score is None or score > 3:
                continue
            c = color_map.get(r["status"], "#999")
            marker = "o" if r["status"] == "accepted" else "x"
            size = 40 if r["status"] == "accepted" else 12
            ax.scatter(r["iteration"], score, c=c, s=size, marker=marker,
                       zorder=3, alpha=0.8)

        best = float("inf")
        fx, fy = [], []
        for r in iters:
            if r["status"] == "accepted":
                score = r.get("full_score") or r.get("quick_score")
                if score and score < best:
                    best = score
                    fx.append(r["iteration"])
                    fy.append(best)
        if fx:
            fx.append(iters[-1]["iteration"])
            fy.append(fy[-1])
            ax.step(fx, fy, where="post", color="#2ecc71", linewidth=2)

        baseline = iters[0].get("full_score") or iters[0].get("quick_score")
        if baseline:
            ax.axhline(y=baseline, color="#999", linestyle="--", linewidth=1)

        ax.set_title(COUNTRY_DISPLAY[country])
        ax.set_xlabel("Iteration")
        ax.set_xlim(-1, max(r["iteration"] for r in iters) + 1)

    axes[0].set_ylabel("MASE (validation era)")

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ecc71",
               markersize=7, label="Accepted"),
        Line2D([0], [0], marker="x", color="#e74c3c", markersize=5, label="Rejected"),
        Line2D([0], [0], color="#2ecc71", linewidth=2, label="Best so far"),
        Line2D([0], [0], color="#999", linestyle="--", linewidth=1, label="Baseline"),
    ]
    axes[-1].legend(handles=legend_elements, loc="upper right", fontsize=7)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig1_search_trajectory.pdf")
    plt.close(fig)
    print("Generated fig1_search_trajectory.pdf")


# ---------------------------------------------------------------------------
# Figure 2: Validation vs test scatter (generalization gap)
# ---------------------------------------------------------------------------


def fig_val_test_scatter():
    df = pd.read_parquet(FE_PATH)
    df["origin_date"] = pd.to_datetime(df["origin_date"])

    method_markers = {
        "random_walk": "s", "arima": "^", "bvar": "v", "var": "D",
        "factor": "P", "elastic_net": "p", "ets": "*",
        "zero_shot": "o", "agent_tuned": "X", "manual_economist": "h",
    }

    fig, ax = plt.subplots(figsize=(5.5, 5))

    for country in COUNTRIES:
        val_scores = _compute_mase_per_method_country(df, country, "validation")
        test_scores = _compute_mase_per_method_country(df, country, "test")
        color = COUNTRY_COLORS[country]

        for variant in val_scores:
            if variant not in test_scores:
                continue
            marker = method_markers.get(variant, "o")
            ax.scatter(val_scores[variant], test_scores[variant],
                       c=color, marker=marker, s=50, alpha=0.8, zorder=3,
                       edgecolors="white", linewidths=0.5)

    # 45-degree line
    lims = [
        min(ax.get_xlim()[0], ax.get_ylim()[0]),
        max(ax.get_xlim()[1], ax.get_ylim()[1]),
    ]
    ax.plot(lims, lims, "--", color="#ccc", linewidth=1, zorder=1)
    ax.fill_between(lims, lims, [lims[1]] * 2, alpha=0.05, color="#e74c3c", zorder=0)
    ax.set_xlim(lims)
    ax.set_ylim(lims)

    ax.set_xlabel("Validation MASE")
    ax.set_ylabel("Test MASE")

    # Country legend
    country_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COUNTRY_COLORS[c],
               markersize=8, label=COUNTRY_DISPLAY[c])
        for c in COUNTRIES
    ]
    # Key method legend
    key_methods = [
        ("random_walk", "s", "RW"), ("arima", "^", "ARIMA"),
        ("zero_shot", "o", "ZS"), ("agent_tuned", "X", "AT"),
    ]
    method_handles = [
        Line2D([0], [0], marker=m, color="w", markerfacecolor="#666",
               markersize=7, label=label)
        for _, m, label in key_methods
    ]
    leg1 = ax.legend(handles=country_handles, loc="upper left", fontsize=7, title="Country")
    ax.add_artist(leg1)
    ax.legend(handles=method_handles, loc="lower right", fontsize=7, title="Method")

    ax.annotate("Overfitting region", xy=(0.3, 0.85), xycoords="axes fraction",
                fontsize=7, color="#e74c3c", alpha=0.5, style="italic")

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig2_val_test_scatter.pdf")
    plt.close(fig)
    print("Generated fig2_val_test_scatter.pdf")


# ---------------------------------------------------------------------------
# Figure 3: Ablation bar chart by country (1x3 subplots)
# ---------------------------------------------------------------------------


def fig_ablation():
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)

    for ax, country in zip(axes, COUNTRIES):
        abl_path = RESULTS_DIR / country / "ablation_leave_one_out.json"
        if not abl_path.exists():
            ax.set_title(COUNTRY_DISPLAY[country])
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue

        abl = json.loads(abl_path.read_text())
        entries = abl["ablations"]

        names = [e["name"].replace("drop_", "").replace("_", "\n") for e in entries]
        degradations = [e.get("degradation_pct", 0) or 0 for e in entries]

        colors = ["#e74c3c" if d > 0 else "#2ecc71" for d in degradations]
        y_pos = np.arange(len(names))

        ax.barh(y_pos, degradations, color=colors, alpha=0.8, edgecolor="white")

        for i, (d, name) in enumerate(zip(degradations, names)):
            if abs(d) > 0.3:
                ax.text(d + 0.1 * np.sign(d), i, f"{d:+.1f}%", va="center",
                        fontsize=7, color="#333")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=7)
        ax.set_title(COUNTRY_DISPLAY[country])
        ax.axvline(0, color="#333", linewidth=0.5)
        ax.set_xlabel("MASE degradation (%)")
        ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig3_ablation.pdf")
    plt.close(fig)
    print("Generated fig3_ablation.pdf")


# ---------------------------------------------------------------------------
# Figure 4: Subperiod grouped bars
# ---------------------------------------------------------------------------


def fig_subperiod():
    df = pd.read_parquet(FE_PATH)
    df["origin_date"] = pd.to_datetime(df["origin_date"])
    test = df[df["is_test"]]

    methods = [
        ("random_walk", "RW", "#95a5a6"),
        ("arima", "ARIMA", "#27ae60"),
        ("zero_shot", "C2-ZS", "#8e44ad"),
        ("agent_tuned", "C2-AT", "#c0392b"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)

    for ax, country in zip(axes, COUNTRIES):
        c_test = test[test["country"] == country]
        c_rw = c_test[c_test["model_variant"] == "random_walk"]
        targets = COUNTRY_TARGETS[country]

        sp_names = list(SUBPERIOD_BOUNDS.keys())
        x = np.arange(len(sp_names))
        width = 0.18

        for m_idx, (variant, label, color) in enumerate(methods):
            subset = c_test[c_test["model_variant"] == variant]
            if subset.empty:
                continue

            mase_per_sp = []
            for sp_name, (sp_start, sp_end) in SUBPERIOD_BOUNDS.items():
                sp_data = subset[(subset["origin_date"] >= sp_start) & (subset["origin_date"] <= sp_end)]
                sp_rw = c_rw[(c_rw["origin_date"] >= sp_start) & (c_rw["origin_date"] <= sp_end)]

                mase_vals = []
                for t in targets:
                    for h in HORIZONS:
                        m_sub = sp_data[(sp_data["target"] == t) & (sp_data["horizon"] == h)]
                        r_sub = sp_rw[(sp_rw["target"] == t) & (sp_rw["horizon"] == h)]
                        if m_sub.empty or r_sub.empty:
                            continue
                        shared = m_sub[["origin_date", "abs_error"]].merge(
                            r_sub[["origin_date", "abs_error"]],
                            on="origin_date", suffixes=("_m", "_rw"),
                        )
                        if shared.empty:
                            continue
                        mase = shared["abs_error_m"].mean() / shared["abs_error_rw"].mean()
                        mase_vals.append(mase)
                mase_per_sp.append(float(np.mean(mase_vals)) if mase_vals else 0)

            offset = (m_idx - 1.5) * width
            ax.bar(x + offset, mase_per_sp, width, label=label, color=color, alpha=0.85)

        ax.axhline(1.0, color="#999", linestyle="--", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(sp_names, fontsize=7)
        ax.set_title(COUNTRY_DISPLAY[country])

    axes[0].set_ylabel("Average MASE")
    axes[-1].legend(loc="upper right", fontsize=7, ncol=2)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig4_subperiod.pdf")
    plt.close(fig)
    print("Generated fig4_subperiod.pdf")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FIGURE_GENERATORS = {
    "search_trajectory": fig_search_trajectory,
    "val_test_scatter": fig_val_test_scatter,
    "ablation": fig_ablation,
    "subperiod": fig_subperiod,
}


def main():
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--figures", nargs="*", default=list(FIGURE_GENERATORS.keys()),
                        help="Which figures to generate")
    args = parser.parse_args()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating figures in {FIGURES_DIR}...")

    for name in args.figures:
        if name not in FIGURE_GENERATORS:
            print(f"Unknown figure: {name}")
            continue
        FIGURE_GENERATORS[name]()

    print("\nDone.")


if __name__ == "__main__":
    main()
