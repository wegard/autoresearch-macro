"""Visual calibration diagnostics for Chronos-2 quantile bands.

Reads results/coverage/<country>.parquet (produced by coverage_backtest.py)
and emits two multi-panel figures under results/coverage/figures/:

  calibration_curves.{png,pdf}
      3 rows (countries) × 4 cols (targets) of calibration curves.
      Each panel plots empirical P(actual ≤ Q(τ)) against nominal τ
      for τ ∈ {0.1, 0.25, 0.5, 0.75, 0.9}, one line per horizon bucket
      (h=1, h=3, h=6, h=12). 45° diagonal is the perfect-calibration
      reference. Under-coverage shows as curves bowing BELOW the
      lower diagonal half and ABOVE the upper diagonal half (actuals
      falling outside the model's claimed bands).

  pit_histograms.{png,pdf}
      3 × 4 grid of PIT histograms with bin edges at {0, 0.1, 0.25,
      0.5, 0.75, 0.9, 1} — matching the 5 quantile levels we have.
      Density normalised so a perfectly calibrated forecast shows
      uniform density = 1 (red dashed reference). Taller bars in
      the tail bins ([0, 0.1] and [0.9, 1]) indicate too much tail
      mass in realisations — i.e., predictive bands too narrow.

Usage:
  uv run python src/coverage_plots.py
  uv run python src/coverage_plots.py --input-dir results/coverage \\
      --output-dir results/coverage/figures
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "results" / "coverage"
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "coverage" / "figures"

COUNTRIES: list[str] = ["norway", "canada", "sweden"]
COUNTRY_DISPLAY = {"norway": "Norway", "canada": "Canada", "sweden": "Sweden"}

TARGETS: list[str] = ["cpi", "industrial_production", "retail_sales", "unemployment"]
TARGET_DISPLAY = {
    "cpi": "CPI",
    "industrial_production": "Industrial production",
    "retail_sales": "Retail sales",
    "unemployment": "Unemployment",
}

QUANTILE_LEVELS = [0.1, 0.25, 0.5, 0.75, 0.9]

# Horizon buckets to show as separate lines on calibration curves.
HORIZON_BUCKETS = [1, 3, 6, 12]
HORIZON_COLORS = {1: "#1f77b4", 3: "#ff7f0e", 6: "#2ca02c", 12: "#d62728"}

# PIT bin edges matching the quantile levels we have. Uniform density
# reference = 1.0 across [0, 1].
PIT_BINS = np.array([0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])


def load_all(input_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for country in COUNTRIES:
        path = input_dir / f"{country}.parquet"
        if not path.exists():
            logger.warning("Missing %s — skipping", path)
            continue
        df = pd.read_parquet(path)
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No country parquet files under {input_dir}")
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Calibration curves
# ---------------------------------------------------------------------------


def _empirical_at_tau(group: pd.DataFrame, tau: float) -> float | None:
    """Empirical P(actual ≤ Q(τ)) for a given quantile τ."""
    col = f"q{int(round(tau * 100))}"
    if col not in group.columns:
        return None
    clean = group[[col, "actual"]].dropna()
    if clean.empty:
        return None
    return float((clean["actual"] <= clean[col]).mean())


def draw_calibration_curves(df: pd.DataFrame, out_path_png: Path, out_path_pdf: Path) -> None:
    """3×4 grid of calibration curves."""
    fig, axes = plt.subplots(
        len(COUNTRIES), len(TARGETS),
        figsize=(13, 9), sharex=True, sharey=True,
    )

    for i, country in enumerate(COUNTRIES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            cdf = df[(df["country"] == country) & (df["target"] == target)]
            if cdf.empty:
                ax.set_facecolor("#f5f5f5")
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        transform=ax.transAxes, fontsize=10, color="#999")
                ax.set_xticks([])
                ax.set_yticks([])
                if i == 0:
                    ax.set_title(TARGET_DISPLAY[target], fontsize=11)
                if j == 0:
                    ax.set_ylabel(COUNTRY_DISPLAY[country], fontsize=11)
                continue

            # 45° reference.
            ax.plot([0, 1], [0, 1], color="#888", linestyle="--", linewidth=0.8, zorder=1)

            for h in HORIZON_BUCKETS:
                group = cdf[cdf["horizon"] == h]
                if group.empty:
                    continue
                emp = [_empirical_at_tau(group, tau) for tau in QUANTILE_LEVELS]
                emp_pairs = [(t, e) for t, e in zip(QUANTILE_LEVELS, emp) if e is not None]
                if not emp_pairs:
                    continue
                taus, emps = zip(*emp_pairs)
                ax.plot(taus, emps, marker="o", markersize=4, linewidth=1.4,
                        color=HORIZON_COLORS[h], label=f"h={h}", zorder=2)

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.grid(True, color="#eee", linewidth=0.5)

            if i == 0:
                ax.set_title(TARGET_DISPLAY[target], fontsize=11)
            if j == 0:
                ax.set_ylabel(COUNTRY_DISPLAY[country] + "\nEmpirical P(actual ≤ Q(τ))",
                              fontsize=10)
            if i == len(COUNTRIES) - 1:
                ax.set_xlabel("Nominal τ", fontsize=10)

    # Single legend at top.
    handles = [plt.Line2D([0], [0], color=HORIZON_COLORS[h], marker="o",
                           markersize=4, label=f"h={h}")
               for h in HORIZON_BUCKETS]
    handles.append(plt.Line2D([0], [0], color="#888", linestyle="--", label="Perfect calibration"))
    fig.legend(handles=handles, loc="upper center",
               bbox_to_anchor=(0.5, 0.995), ncol=len(handles), frameon=False, fontsize=10)

    fig.suptitle("Calibration curves — Chronos-2 predictive quantiles vs realised frequencies",
                 fontsize=12, y=0.945)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_path_png, dpi=150, bbox_inches="tight")
    fig.savefig(out_path_pdf, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", out_path_png)
    logger.info("Wrote %s", out_path_pdf)


# ---------------------------------------------------------------------------
# PIT histograms (bin-based, matching quantile grid)
# ---------------------------------------------------------------------------


def _classify_into_pit_bin(df: pd.DataFrame) -> np.ndarray:
    """Assign each row to a PIT bin index (0..5) based on which quantile
    interval the actual falls into. Returns the bin MIDPOINT so the
    histogram uses exact bin widths."""
    a = df["actual"].to_numpy()
    q10 = df["q10"].to_numpy()
    q25 = df["q25"].to_numpy()
    q50 = df["q50"].to_numpy()
    q75 = df["q75"].to_numpy()
    q90 = df["q90"].to_numpy()

    # For histogram purposes, assign each row a sentinel x-value inside
    # its bin. Bin edges are PIT_BINS.
    midpoints = (PIT_BINS[:-1] + PIT_BINS[1:]) / 2.0
    bin_idx = np.full(len(df), 0, dtype=int)
    bin_idx[a <= q10] = 0
    bin_idx[(a > q10) & (a <= q25)] = 1
    bin_idx[(a > q25) & (a <= q50)] = 2
    bin_idx[(a > q50) & (a <= q75)] = 3
    bin_idx[(a > q75) & (a <= q90)] = 4
    bin_idx[a > q90] = 5
    return midpoints[bin_idx]


def draw_pit_histograms(df: pd.DataFrame, out_path_png: Path, out_path_pdf: Path) -> None:
    """3×4 grid of PIT histograms, pooled over horizons."""
    fig, axes = plt.subplots(
        len(COUNTRIES), len(TARGETS),
        figsize=(13, 9), sharex=True, sharey=True,
    )

    bin_widths = np.diff(PIT_BINS)

    for i, country in enumerate(COUNTRIES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            cdf = df[(df["country"] == country) & (df["target"] == target)]
            if cdf.empty:
                ax.set_facecolor("#f5f5f5")
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        transform=ax.transAxes, fontsize=10, color="#999")
                ax.set_xticks([])
                ax.set_yticks([])
                if i == 0:
                    ax.set_title(TARGET_DISPLAY[target], fontsize=11)
                if j == 0:
                    ax.set_ylabel(COUNTRY_DISPLAY[country], fontsize=11)
                continue

            pit_points = _classify_into_pit_bin(cdf)
            counts, _ = np.histogram(pit_points, bins=PIT_BINS)
            total = counts.sum()
            densities = counts / total / bin_widths if total > 0 else np.zeros_like(counts)

            # Bar chart. Color tail bins differently to highlight them.
            colors = ["#d62728", "#ff9896", "#aec7e8", "#aec7e8", "#ff9896", "#d62728"]
            for k, (left, width, d, color) in enumerate(zip(
                PIT_BINS[:-1], bin_widths, densities, colors, strict=True
            )):
                ax.add_patch(Rectangle(
                    (left, 0), width, d,
                    facecolor=color, edgecolor="#333", linewidth=0.6, alpha=0.85,
                ))

            # Uniform reference line at density = 1.
            ax.axhline(1.0, color="#555", linestyle="--", linewidth=0.9, zorder=3)

            ax.set_xlim(0, 1)
            ax.set_ylim(0, max(2.5, densities.max() * 1.15))
            ax.set_xticks(PIT_BINS)
            ax.set_xticklabels([f"{x:.2f}" for x in PIT_BINS], fontsize=8)
            ax.grid(True, axis="y", color="#eee", linewidth=0.5)

            if i == 0:
                ax.set_title(TARGET_DISPLAY[target], fontsize=11)
            if j == 0:
                ax.set_ylabel(COUNTRY_DISPLAY[country] + "\nDensity", fontsize=10)
            if i == len(COUNTRIES) - 1:
                ax.set_xlabel("PIT value", fontsize=10)

    handles = [
        Rectangle((0, 0), 1, 1, facecolor="#d62728", alpha=0.85, label="Tail bins (|u|<0.1 from 0 or 1)"),
        Rectangle((0, 0), 1, 1, facecolor="#ff9896", alpha=0.85, label="Shoulder bins"),
        Rectangle((0, 0), 1, 1, facecolor="#aec7e8", alpha=0.85, label="Middle bins"),
        plt.Line2D([0], [0], color="#555", linestyle="--", label="Uniform (perfect calibration)"),
    ]
    fig.legend(handles=handles, loc="upper center",
               bbox_to_anchor=(0.5, 0.995), ncol=len(handles), frameon=False, fontsize=9)

    fig.suptitle("PIT histograms — pooled over test-era origins and horizons (1–12 months)",
                 fontsize=12, y=0.945)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_path_png, dpi=150, bbox_inches="tight")
    fig.savefig(out_path_pdf, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", out_path_png)
    logger.info("Wrote %s", out_path_pdf)


# ---------------------------------------------------------------------------
# Summary stats accompanying the plots
# ---------------------------------------------------------------------------


def emit_tail_stats(df: pd.DataFrame, out_path: Path) -> None:
    """Compute fraction of actuals in each PIT bin, per (country, target).
    Companion to the histogram figure — quick numerical reference."""
    rows: list[dict] = []
    for country in COUNTRIES:
        for target in TARGETS:
            cdf = df[(df["country"] == country) & (df["target"] == target)]
            if cdf.empty:
                continue
            pit_points = _classify_into_pit_bin(cdf)
            counts, _ = np.histogram(pit_points, bins=PIT_BINS)
            total = counts.sum()
            if total == 0:
                continue
            fractions = counts / total
            row = {
                "country": country,
                "target": target,
                "n": int(total),
                "frac_below_q10": round(float(fractions[0]), 4),
                "frac_above_q90": round(float(fractions[-1]), 4),
                "frac_in_80pct_band": round(float(fractions[1:-1].sum()), 4),
                "frac_in_50pct_band": round(float(fractions[2:4].sum()), 4),
            }
            rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(out_path, index=False)
    logger.info("Wrote %s", out_path)
    print()
    print("PIT tail stats (fraction of obs in each region; expected 10% / 80% / 10%):")
    print(table.to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    df = load_all(args.input_dir)
    logger.info("Loaded %d rows across %d countries",
                len(df), df["country"].nunique())

    args.output_dir.mkdir(parents=True, exist_ok=True)

    draw_calibration_curves(
        df,
        args.output_dir / "calibration_curves.png",
        args.output_dir / "calibration_curves.pdf",
    )
    draw_pit_histograms(
        df,
        args.output_dir / "pit_histograms.png",
        args.output_dir / "pit_histograms.pdf",
    )
    emit_tail_stats(df, args.output_dir / "pit_tail_stats.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
