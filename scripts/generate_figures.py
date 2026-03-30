"""Generate all paper figures.

Produces 5 PDF figures in paper/figures/ for inclusion in main.tex.

Usage:
    uv run python scripts/generate_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "paper" / "figures"
RESULTS_DIR = PROJECT_ROOT / "results"

# Academic style
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

COLORS = {
    "accepted": "#2ecc71",
    "rejected": "#e74c3c",
    "error": "#f39c12",
    "rw": "#95a5a6",
    "arima": "#27ae60",
    "c2zs": "#8e44ad",
    "c2at": "#c0392b",
    "validation": "#3498db",
    "test": "#e74c3c",
}


def fig1_search_trajectory():
    """Figure 1: Search trajectory with accepted/rejected dots and frontier."""
    # Load the LLM search log (last run only — iterations 0-50 from the final run)
    log_path = RESULTS_DIR / "search_log.jsonl"
    if not log_path.exists():
        print("No search log found, skipping Fig 1")
        return

    # Parse all iterations, take the last run (starts with iter 0)
    all_iters = []
    for line in log_path.read_text().strip().split("\n"):
        if line.strip():
            all_iters.append(json.loads(line))

    # Find the last run's baseline (last occurrence of iteration 0)
    last_run_start = 0
    for i, r in enumerate(all_iters):
        if r["iteration"] == 0:
            last_run_start = i
    iters = all_iters[last_run_start:]

    fig, ax = plt.subplots(figsize=(7, 3.5))

    # Plot all attempts
    for r in iters:
        score = r.get("full_score") or r.get("quick_score")
        if score is None or score > 3:
            continue
        color = COLORS.get(r["status"], "#999")
        marker = "o" if r["status"] == "accepted" else "x"
        size = 40 if r["status"] == "accepted" else 15
        ax.scatter(r["iteration"], score, c=color, s=size, marker=marker,
                   zorder=3, alpha=0.8)

    # Best frontier line
    best = float("inf")
    frontier_x, frontier_y = [], []
    for r in iters:
        if r["status"] == "accepted":
            score = r.get("full_score") or r.get("quick_score")
            if score and score < best:
                best = score
                frontier_x.append(r["iteration"])
                frontier_y.append(best)
    if frontier_x:
        # Extend to the end
        frontier_x.append(iters[-1]["iteration"])
        frontier_y.append(frontier_y[-1])
        ax.step(frontier_x, frontier_y, where="post", color=COLORS["accepted"],
                linewidth=2, label="Best so far")

    # Baseline
    baseline = iters[0].get("full_score") or iters[0].get("quick_score")
    if baseline:
        ax.axhline(y=baseline, color="#999", linestyle="--", linewidth=1, label="Baseline")

    ax.set_xlabel("Iteration")
    ax.set_ylabel("MASE (validation era)")
    ax.legend(loc="upper right")
    ax.set_xlim(-1, max(r["iteration"] for r in iters) + 1)

    # Custom legend for dot types
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["accepted"],
               markersize=8, label="Accepted"),
        Line2D([0], [0], marker="x", color=COLORS["rejected"],
               markersize=6, label="Rejected"),
        Line2D([0], [0], color=COLORS["accepted"], linewidth=2, label="Best so far"),
        Line2D([0], [0], color="#999", linestyle="--", linewidth=1, label="Baseline"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")

    fig.savefig(FIGURES_DIR / "fig1_search_trajectory.pdf")
    plt.close(fig)
    print("Generated fig1_search_trajectory.pdf")


def fig2_ablation_scissors():
    """Figure 2: Ablation scissors — validation vs test MASE diverging."""
    ablation_path = RESULTS_DIR / "ablation_results.json"
    if not ablation_path.exists():
        print("No ablation results found, skipping Fig 2")
        return

    data = json.loads(ablation_path.read_text())
    labels = [r["label"] for r in data["validation"]]
    val_scores = [r["mase"] for r in data["validation"]]
    test_scores = [r["mase"] for r in data["test"]]

    # Shorter labels for x-axis
    short_labels = ["Baseline", "+ctx96", "+oil", "+rate", "+US CPI", "+NOK/EUR", "+LoRA"]

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(7, 4))

    ax.plot(x, val_scores, "o-", color=COLORS["validation"], linewidth=2,
            markersize=7, label="Validation (2006–2015)", zorder=3)
    ax.plot(x, test_scores, "s-", color=COLORS["test"], linewidth=2,
            markersize=7, label="Test (2016–2025)", zorder=3)

    # Shade the gap
    ax.fill_between(x, val_scores, test_scores, alpha=0.15, color=COLORS["test"])

    # Annotate the gap percentages
    for i in range(len(x)):
        if val_scores[i] and test_scores[i]:
            gap = (test_scores[i] / val_scores[i] - 1) * 100
            mid = (val_scores[i] + test_scores[i]) / 2
            ax.annotate(f"+{gap:.0f}%", (x[i], mid), fontsize=7,
                        ha="center", color="#666")

    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, rotation=30, ha="right")
    ax.set_ylabel("Average MASE")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fig.savefig(FIGURES_DIR / "fig2_ablation_scissors.pdf")
    plt.close(fig)
    print("Generated fig2_ablation_scissors.pdf")


def fig3_subperiod_bars():
    """Figure 3: Subperiod comparison at h=12."""
    subperiod_path = PROJECT_ROOT / "webapp" / "_data" / "subperiod_metrics.json"
    if not subperiod_path.exists():
        print("No subperiod data found, skipping Fig 3")
        return

    sp_data = json.loads(subperiod_path.read_text())

    methods = ["random_walk", "arima", "chronos2_zs", "chronos2_ft"]
    method_labels = ["Random Walk", "ARIMA", "Chronos-2\n(zero-shot)", "Chronos-2\n(agent-tuned)"]
    method_colors = [COLORS["rw"], COLORS["arima"], COLORS["c2zs"], COLORS["c2at"]]
    subperiods = ["pre_covid", "covid", "post_covid"]
    sp_labels = ["Pre-COVID\n(2016–19)", "COVID\n(2020–21)", "Post-COVID\n(2022+)"]
    variables = ["cpi", "industrial_production", "retail_sales", "unemployment"]

    # Compute avg RMSE across variables at h=12
    bar_data = np.zeros((len(methods), len(subperiods)))
    for i, m in enumerate(methods):
        for j, sp in enumerate(subperiods):
            vals = []
            for v in variables:
                row = next((r for r in sp_data if r["method"] == m and r["subperiod"] == sp
                            and r["variable"] == v and r["horizon"] == 12), None)
                if row and row.get("rmse"):
                    vals.append(row["rmse"])
            bar_data[i, j] = np.mean(vals) if vals else 0

    x = np.arange(len(subperiods))
    width = 0.18

    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (label, color) in enumerate(zip(method_labels, method_colors)):
        offset = (i - 1.5) * width
        ax.bar(x + offset, bar_data[i], width, label=label, color=color, alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(sp_labels)
    ax.set_ylabel("Average RMSE (h=12)")
    ax.legend(loc="upper left", ncol=2, fontsize=7)
    ax.grid(axis="y", alpha=0.3)

    fig.savefig(FIGURES_DIR / "fig3_subperiod_bars.pdf")
    plt.close(fig)
    print("Generated fig3_subperiod_bars.pdf")


def fig4_rolling_error():
    """Figure 4: Rolling forecast error through time."""
    # Load point forecasts and actuals for test + validation eras
    methods = {
        "random_walk": ("Random Walk", COLORS["rw"], "-"),
        "arima": ("ARIMA", COLORS["arima"], "-"),
        "chronos2_zs": ("Chronos-2 (ZS)", COLORS["c2zs"], "-"),
        "chronos2_ft": ("Chronos-2 (AT)", COLORS["c2at"], "--"),
    }

    # Load rolling forecasts from webapp data (has all origins 2006-2025)
    forecasts_path = PROJECT_ROOT / "webapp" / "_data" / "rolling_forecasts.json"
    if not forecasts_path.exists():
        print("No rolling forecasts found, skipping Fig 4")
        return

    fc_data = json.loads(forecasts_path.read_text())

    # For now, use h=1 forecasts from the Chronos runs
    # We need to also get baseline h=1 errors from their point_forecasts
    # This is complex, so let's use a simpler approach: plot the validation+test
    # errors from the existing per-variable results

    # Actually, let's use the forecast data we have for chronos and compute
    # a simulated rolling error for all targets
    h1_records = [r for r in fc_data if r["h"] == 1 and r["forecast"] is not None and r["actual"] is not None]

    if not h1_records:
        print("No h=1 forecast data, skipping Fig 4")
        return

    # Compute average |error| across all 4 targets per origin date
    from collections import defaultdict
    errors_by_date: dict[str, list[float]] = defaultdict(list)
    for r in h1_records:
        err = abs(r["actual"] - r["forecast"])
        errors_by_date[r["target_date"]].append(err)

    dates = sorted(errors_by_date.keys())
    avg_errors = [np.mean(errors_by_date[d]) for d in dates]
    dates_dt = [pd.Timestamp(d) for d in dates]

    # Rolling 12-month average
    if len(avg_errors) >= 12:
        rolling = pd.Series(avg_errors, index=dates_dt).rolling(12).mean()
    else:
        rolling = pd.Series(avg_errors, index=dates_dt)

    fig, ax = plt.subplots(figsize=(7, 3.5))

    ax.plot(dates_dt, avg_errors, color=COLORS["c2at"], alpha=0.3, linewidth=0.5)
    ax.plot(rolling.index, rolling.values, color=COLORS["c2at"], linewidth=2,
            label="Chronos-2 (agent-tuned, 12m MA)")

    # COVID shading
    ax.axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2021-12-31"),
               alpha=0.1, color="gray", label="COVID period")

    # Validation/test boundary
    ax.axvline(pd.Timestamp("2016-01-01"), color="#999", linestyle="--", linewidth=1)
    ax.text(pd.Timestamp("2016-03-01"), ax.get_ylim()[1] * 0.9, "Test →",
            fontsize=8, color="#999")

    ax.set_xlabel("Date")
    ax.set_ylabel("Average |error| (h=1, all targets)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(axis="y", alpha=0.3)

    fig.savefig(FIGURES_DIR / "fig4_rolling_error.pdf")
    plt.close(fig)
    print("Generated fig4_rolling_error.pdf")


def fig5_covariate_timeline():
    """Figure 5: Covariate discovery timeline."""
    accepted = [
        (0, "Baseline", 1.9443),
        (9, "+ctx96", 1.8635),
        (15, "+oil", 1.8472),
        (18, "+rate", 1.8326),
        (27, "+US CPI", 1.8158),
        (39, "+NOK/EUR", 1.8129),
        (45, "+LoRA", 1.8129),
    ]

    fig, ax = plt.subplots(figsize=(7, 2.5))

    # Timeline bar
    ax.barh(0, 50, left=0, height=0.3, color="#ecf0f1", edgecolor="#bdc3c7")

    # Markers at accepted iterations
    for iteration, label, score in accepted:
        color = COLORS["accepted"] if iteration > 0 else "#2c3e50"
        ax.scatter(iteration, 0, s=80, color=color, zorder=5, edgecolors="white", linewidths=1)
        ax.annotate(f"{label}\n{score:.3f}",
                    (iteration, 0), xytext=(0, 18), textcoords="offset points",
                    ha="center", fontsize=7, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color="#ccc", lw=0.5))

    # Rejected dots (lighter, smaller)
    rejected_iters = [i for i in range(1, 51)
                      if i not in [a[0] for a in accepted]]
    for it in rejected_iters:
        ax.scatter(it, 0, s=8, color=COLORS["rejected"], alpha=0.4, zorder=4)

    ax.set_xlim(-2, 52)
    ax.set_ylim(-0.8, 1.2)
    ax.set_xlabel("Iteration")
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    fig.savefig(FIGURES_DIR / "fig5_covariate_timeline.pdf")
    plt.close(fig)
    print("Generated fig5_covariate_timeline.pdf")


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating figures in {FIGURES_DIR}...")

    fig1_search_trajectory()
    fig2_ablation_scissors()
    fig3_subperiod_bars()
    fig4_rolling_error()
    fig5_covariate_timeline()

    print("\nDone.")


if __name__ == "__main__":
    main()
