"""Compare two coverage backtests (e.g., fine-tuned vs zero-shot).

Reads per-country parquet files from two directories produced by
coverage_backtest.py and renders overlay figures that isolate the
effect of the differing configuration (typically LoRA fine-tuning
vs plain Chronos-2 zero-shot).

Outputs under --output-dir:

  calibration_curves_compare.{png,pdf}
      3×4 grid. In each panel, dashed lines = baseline (fine-tuned),
      solid lines = variant (zero-shot). One colour per horizon bucket.

  pit_histograms_compare.{png,pdf}
      3×4 grid of PIT histograms with side-by-side bars, baseline in
      red and variant in blue, uniform reference line at density = 1.

  coverage_delta.csv
      Per (country, target, horizon, band) table of empirical
      coverage for each config + delta (variant − baseline).

Usage:
  uv run python src/coverage_compare.py \\
      --baseline-dir results/coverage \\
      --variant-dir  results/coverage_zs \\
      --baseline-label "Fine-tuned" \\
      --variant-label  "Zero-shot"
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from coverage_plots import (
    COUNTRIES,
    COUNTRY_DISPLAY,
    HORIZON_BUCKETS,
    HORIZON_COLORS,
    PIT_BINS,
    QUANTILE_LEVELS,
    TARGET_DISPLAY,
    TARGETS,
    _classify_into_pit_bin,
    _empirical_at_tau,
    load_all,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = PROJECT_ROOT / "results" / "coverage"
DEFAULT_VARIANT = PROJECT_ROOT / "results" / "coverage_zs"
DEFAULT_OUTPUT = PROJECT_ROOT / "results" / "coverage_compare"


def draw_calibration_compare(
    base: pd.DataFrame, var: pd.DataFrame,
    labels: tuple[str, str],
    out_png: Path, out_pdf: Path,
) -> None:
    base_label, var_label = labels
    fig, axes = plt.subplots(
        len(COUNTRIES), len(TARGETS),
        figsize=(13, 9), sharex=True, sharey=True,
    )
    for i, country in enumerate(COUNTRIES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            bdf = base[(base["country"] == country) & (base["target"] == target)]
            vdf = var[(var["country"] == country) & (var["target"] == target)]
            if bdf.empty and vdf.empty:
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

            ax.plot([0, 1], [0, 1], color="#888", linestyle=":", linewidth=0.8, zorder=1)

            for horizon in HORIZON_BUCKETS:
                for df, linestyle in ((bdf, "--"), (vdf, "-")):
                    g = df[df["horizon"] == horizon]
                    if g.empty:
                        continue
                    emp = [_empirical_at_tau(g, tau) for tau in QUANTILE_LEVELS]
                    pairs = [(t, e) for t, e in zip(QUANTILE_LEVELS, emp) if e is not None]
                    if not pairs:
                        continue
                    taus, emps = zip(*pairs)
                    ax.plot(taus, emps, marker="o", markersize=3,
                            linestyle=linestyle, linewidth=1.2,
                            color=HORIZON_COLORS[horizon], alpha=0.9, zorder=2)

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.grid(True, color="#eee", linewidth=0.5)
            if i == 0:
                ax.set_title(TARGET_DISPLAY[target], fontsize=11)
            if j == 0:
                ax.set_ylabel(COUNTRY_DISPLAY[country] + "\nEmpirical", fontsize=10)
            if i == len(COUNTRIES) - 1:
                ax.set_xlabel("Nominal τ", fontsize=10)

    h_horizon = [plt.Line2D([0], [0], color=HORIZON_COLORS[h], marker="o",
                            markersize=4, label=f"h={h}")
                 for h in HORIZON_BUCKETS]
    h_style = [
        plt.Line2D([0], [0], color="#333", linestyle="--", label=base_label),
        plt.Line2D([0], [0], color="#333", linestyle="-", label=var_label),
        plt.Line2D([0], [0], color="#888", linestyle=":", label="Perfect"),
    ]
    fig.legend(handles=h_horizon + h_style, loc="upper center",
               bbox_to_anchor=(0.5, 0.995), ncol=len(h_horizon) + len(h_style),
               frameon=False, fontsize=9)
    fig.suptitle(f"Calibration curves — {base_label} (dashed) vs {var_label} (solid)",
                 fontsize=12, y=0.945)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", out_png)
    logger.info("Wrote %s", out_pdf)


def draw_pit_compare(
    base: pd.DataFrame, var: pd.DataFrame,
    labels: tuple[str, str],
    out_png: Path, out_pdf: Path,
) -> None:
    base_label, var_label = labels
    fig, axes = plt.subplots(
        len(COUNTRIES), len(TARGETS),
        figsize=(13, 9), sharex=True, sharey=True,
    )

    bin_widths = np.diff(PIT_BINS)

    for i, country in enumerate(COUNTRIES):
        for j, target in enumerate(TARGETS):
            ax = axes[i, j]
            bdf = base[(base["country"] == country) & (base["target"] == target)]
            vdf = var[(var["country"] == country) & (var["target"] == target)]
            if bdf.empty and vdf.empty:
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

            for df, color, shift_sign in (
                (bdf, "#d62728", -1), (vdf, "#1f77b4", +1),
            ):
                if df.empty:
                    continue
                pit_points = _classify_into_pit_bin(df)
                counts, _ = np.histogram(pit_points, bins=PIT_BINS)
                total = counts.sum()
                densities = counts / total / bin_widths if total > 0 else np.zeros_like(counts)
                for left, width, d in zip(PIT_BINS[:-1], bin_widths, densities, strict=True):
                    ax.add_patch(Rectangle(
                        (left + shift_sign * width / 4, 0),
                        width / 2, d,
                        facecolor=color, edgecolor="#333", linewidth=0.4, alpha=0.8,
                    ))

            ax.axhline(1.0, color="#555", linestyle="--", linewidth=0.9, zorder=3)
            ax.set_xlim(0, 1)
            max_d = 0.0
            for df in (bdf, vdf):
                if df.empty:
                    continue
                pit_points = _classify_into_pit_bin(df)
                counts, _ = np.histogram(pit_points, bins=PIT_BINS)
                total = counts.sum()
                densities = counts / total / bin_widths if total > 0 else np.zeros_like(counts)
                max_d = max(max_d, float(densities.max()))
            ax.set_ylim(0, max(2.5, max_d * 1.15))
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
        Rectangle((0, 0), 1, 1, facecolor="#d62728", alpha=0.8, label=base_label),
        Rectangle((0, 0), 1, 1, facecolor="#1f77b4", alpha=0.8, label=var_label),
        plt.Line2D([0], [0], color="#555", linestyle="--", label="Uniform (perfect)"),
    ]
    fig.legend(handles=handles, loc="upper center",
               bbox_to_anchor=(0.5, 0.995), ncol=len(handles), frameon=False, fontsize=10)
    fig.suptitle(f"PIT histograms — {base_label} vs {var_label}",
                 fontsize=12, y=0.945)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s", out_png)
    logger.info("Wrote %s", out_pdf)


def emit_coverage_delta(
    base: pd.DataFrame, var: pd.DataFrame, labels: tuple[str, str], out_csv: Path,
) -> None:
    from coverage_backtest import COVERAGE_BANDS

    base_label, var_label = labels
    rows = []
    keys = sorted(set(
        [(c, t, h) for c, t, h in base[["country", "target", "horizon"]].drop_duplicates().itertuples(index=False)]
        + [(c, t, h) for c, t, h in var[["country", "target", "horizon"]].drop_duplicates().itertuples(index=False)]
    ))
    for country, target, horizon in keys:
        for lo, hi, nominal in COVERAGE_BANDS:
            lo_col = f"q{int(round(lo * 100))}"
            hi_col = f"q{int(round(hi * 100))}"

            def _cov(df: pd.DataFrame) -> tuple[float | None, int]:
                g = df[(df["country"] == country) & (df["target"] == target)
                       & (df["horizon"] == horizon)]
                if g.empty or lo_col not in g.columns or hi_col not in g.columns:
                    return None, 0
                within = (g["actual"] >= g[lo_col]) & (g["actual"] <= g[hi_col])
                n = int(within.count())
                if n == 0:
                    return None, 0
                return float(within.sum() / n), n

            b_cov, b_n = _cov(base)
            v_cov, v_n = _cov(var)
            rows.append({
                "country": country,
                "target": target,
                "horizon": int(horizon),
                "band": f"{int(lo * 100)}-{int(hi * 100)}%",
                "nominal": nominal,
                f"{base_label}_empirical": round(b_cov, 4) if b_cov is not None else None,
                f"{var_label}_empirical": round(v_cov, 4) if v_cov is not None else None,
                "delta": round(v_cov - b_cov, 4) if b_cov is not None and v_cov is not None else None,
                "n": max(b_n, v_n),
            })
    table = pd.DataFrame(rows)
    table.to_csv(out_csv, index=False)
    logger.info("Wrote %s", out_csv)

    # Overall summary
    summary = table.groupby("band").agg(
        **{
            f"{base_label}_mean": (f"{base_label}_empirical", "mean"),
            f"{var_label}_mean": (f"{var_label}_empirical", "mean"),
            "delta_mean": ("delta", "mean"),
        }
    ).reset_index()
    print()
    print("Overall empirical coverage comparison (mean across country×target×horizon):")
    print(summary.to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--variant-dir", type=Path, default=DEFAULT_VARIANT)
    parser.add_argument("--baseline-label", default="Fine-tuned")
    parser.add_argument("--variant-label", default="Zero-shot")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    base = load_all(args.baseline_dir)
    var = load_all(args.variant_dir)
    logger.info("Baseline: %d rows, Variant: %d rows", len(base), len(var))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    labels = (args.baseline_label, args.variant_label)

    draw_calibration_compare(
        base, var, labels,
        args.output_dir / "calibration_curves_compare.png",
        args.output_dir / "calibration_curves_compare.pdf",
    )
    draw_pit_compare(
        base, var, labels,
        args.output_dir / "pit_histograms_compare.png",
        args.output_dir / "pit_histograms_compare.pdf",
    )
    emit_coverage_delta(base, var, labels, args.output_dir / "coverage_delta.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
