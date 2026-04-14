r"""Paper-ready LaTeX tables for the Chronos-2 calibration section.

Emits three \\input{}-able fragments under paper/tables/:

  tab_calibration.tex
      Empirical coverage of the 80% (q10-q90) and 50% (q25-q75)
      predictive bands, per country × target, for the fine-tuned
      informed search (FT), the zero-shot baseline (ZS), and the
      post-calibration run (Cal) when results/coverage_calibrated/
      is present. Final row is a pooled mean across all (country
      × target × horizon) triples. Values more than 15 pp off
      nominal are bolded.

  tab_calibration_bias.tex
      PIT tail fractions on the zero-shot run — fraction of
      actuals below q10, within the 80% band (q10-q90), and above
      q90, per country × target. Expected under perfect calibration
      are 10% / 80% / 10%. Serves to illustrate the
      foundation-model's directional biases (e.g., Canada retail
      sales with ~42% above q90).

  tab_calibration_macros.tex
      \\newcommand{} macros for inline references in the paper
      body — pooled FT/ZS/Cal coverage numbers, gaps in percentage
      points, and the names+fractions of the worst directional
      biases.

Inputs:
  results/coverage/<country>.parquet              (FT, test era)
  results/coverage_zs/<country>.parquet           (ZS, test era)
  results/coverage_calibrated/<country>.parquet   (optional, post-cal)

Usage:
  uv run python src/coverage_tables.py
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from coverage_plots import (
    COUNTRIES,
    COUNTRY_DISPLAY,
    PIT_BINS,
    TARGET_DISPLAY,
    TARGETS,
    _classify_into_pit_bin,
    load_all,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FT = PROJECT_ROOT / "results" / "coverage"
DEFAULT_ZS = PROJECT_ROOT / "results" / "coverage_zs"
DEFAULT_CAL = PROJECT_ROOT / "results" / "coverage_calibrated"
DEFAULT_OUT = PROJECT_ROOT / "paper" / "tables"

NOMINAL = {"80-90": 0.8, "50-75": 0.5}
COVERAGE_BANDS = [(0.1, 0.9, 0.8), (0.25, 0.75, 0.5)]


def _empirical_band_coverage(
    df: pd.DataFrame, lo_q: float, hi_q: float,
) -> float | None:
    """Fraction of actuals within [Q(lo_q), Q(hi_q)], pooled over
    horizons and origins."""
    lo_col = f"q{int(round(lo_q * 100))}"
    hi_col = f"q{int(round(hi_q * 100))}"
    if df.empty or lo_col not in df.columns or hi_col not in df.columns:
        return None
    within = (df["actual"] >= df[lo_col]) & (df["actual"] <= df[hi_col])
    n = int(within.count())
    if n == 0:
        return None
    return float(within.sum() / n)


def _format_cov(value: float | None, nominal: float) -> str:
    """LaTeX cell for a coverage value, bolded when the gap is >= 15pp."""
    if value is None:
        return "--"
    gap = abs(value - nominal)
    cell = f"{value:.3f}"
    if gap >= 0.15:
        return rf"\textbf{{{cell}}}"
    return cell


def _build_calibration_rows(
    base: pd.DataFrame, var: pd.DataFrame, cal: pd.DataFrame | None,
) -> tuple[list[dict], dict[str, float | None]]:
    """Per (country, target) rows for the main calibration table.

    `cal` is optional; when None the calibrated columns are skipped.
    """
    rows: list[dict] = []
    for country in COUNTRIES:
        for target in TARGETS:
            bdf = base[(base["country"] == country) & (base["target"] == target)]
            vdf = var[(var["country"] == country) & (var["target"] == target)]
            cdf = (
                cal[(cal["country"] == country) & (cal["target"] == target)]
                if cal is not None
                else None
            )
            if bdf.empty and vdf.empty and (cdf is None or cdf.empty):
                continue
            row = {
                "country": country,
                "target": target,
                "ft80": _empirical_band_coverage(bdf, 0.1, 0.9),
                "zs80": _empirical_band_coverage(vdf, 0.1, 0.9),
                "ft50": _empirical_band_coverage(bdf, 0.25, 0.75),
                "zs50": _empirical_band_coverage(vdf, 0.25, 0.75),
            }
            if cdf is not None:
                row["cal80"] = _empirical_band_coverage(cdf, 0.1, 0.9)
                row["cal50"] = _empirical_band_coverage(cdf, 0.25, 0.75)
            rows.append(row)

    pooled: dict[str, float | None] = {
        "ft80": _empirical_band_coverage(base, 0.1, 0.9),
        "zs80": _empirical_band_coverage(var, 0.1, 0.9),
        "ft50": _empirical_band_coverage(base, 0.25, 0.75),
        "zs50": _empirical_band_coverage(var, 0.25, 0.75),
    }
    if cal is not None:
        pooled["cal80"] = _empirical_band_coverage(cal, 0.1, 0.9)
        pooled["cal50"] = _empirical_band_coverage(cal, 0.25, 0.75)
    return rows, pooled


def write_calibration_table(
    rows: list[dict],
    pooled: dict[str, float | None],
    out_path: Path,
    include_cal: bool,
) -> None:
    lines: list[str] = []
    if include_cal:
        lines.append(r"\begin{tabular}{llcccccc}")
        lines.append(r"\toprule")
        lines.append(
            r" & & \multicolumn{3}{c}{80\% band (q10--q90)} "
            r"& \multicolumn{3}{c}{50\% band (q25--q75)} \\"
        )
        lines.append(r"\cmidrule(lr){3-5} \cmidrule(lr){6-8}")
        lines.append(
            r"Country & Target & FT & ZS & Cal & FT & ZS & Cal \\"
        )
    else:
        lines.append(r"\begin{tabular}{llcccc}")
        lines.append(r"\toprule")
        lines.append(
            r" & & \multicolumn{2}{c}{80\% band (q10--q90)} "
            r"& \multicolumn{2}{c}{50\% band (q25--q75)} \\"
        )
        lines.append(r"\cmidrule(lr){3-4} \cmidrule(lr){5-6}")
        lines.append(r"Country & Target & Fine-tuned & Zero-shot & Fine-tuned & Zero-shot \\")
    lines.append(r"\midrule")

    current_country: str | None = None
    for i, row in enumerate(rows):
        country = row["country"]
        target = row["target"]
        country_cell = ""
        if country != current_country:
            if current_country is not None:
                lines.append(r"\midrule")
            n_remaining = sum(1 for r in rows[i:] if r["country"] == country)
            country_cell = rf"\multirow{{{n_remaining}}}{{*}}{{{COUNTRY_DISPLAY[country]}}}"
            current_country = country

        cells = [country_cell, TARGET_DISPLAY[target]]
        cells.append(_format_cov(row["ft80"], 0.8))
        cells.append(_format_cov(row["zs80"], 0.8))
        if include_cal:
            cells.append(_format_cov(row.get("cal80"), 0.8))
        cells.append(_format_cov(row["ft50"], 0.5))
        cells.append(_format_cov(row["zs50"], 0.5))
        if include_cal:
            cells.append(_format_cov(row.get("cal50"), 0.5))
        lines.append(" & ".join(cells) + r" \\")

    lines.append(r"\midrule")
    pooled_cells = [
        r"\multicolumn{2}{l}{\emph{Pooled (country$\times$target$\times$horizon)}}",
        _format_cov(pooled["ft80"], 0.8),
        _format_cov(pooled["zs80"], 0.8),
    ]
    if include_cal:
        pooled_cells.append(_format_cov(pooled.get("cal80"), 0.8))
    pooled_cells.append(_format_cov(pooled["ft50"], 0.5))
    pooled_cells.append(_format_cov(pooled["zs50"], 0.5))
    if include_cal:
        pooled_cells.append(_format_cov(pooled.get("cal50"), 0.5))
    lines.append(" & ".join(pooled_cells) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    out_path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote %s", out_path)


def _build_bias_rows(var: pd.DataFrame) -> list[dict]:
    """PIT tail fractions on the zero-shot run."""
    rows: list[dict] = []
    for country in COUNTRIES:
        for target in TARGETS:
            df = var[(var["country"] == country) & (var["target"] == target)]
            if df.empty:
                continue
            pit = _classify_into_pit_bin(df)
            counts, _ = np.histogram(pit, bins=PIT_BINS)
            total = counts.sum()
            if total == 0:
                continue
            fracs = counts / total
            rows.append({
                "country": country,
                "target": target,
                "below_q10": float(fracs[0]),
                "within": float(fracs[1:-1].sum()),
                "above_q90": float(fracs[-1]),
                "n": int(total),
            })
    return rows


def _format_bias(value: float, expected: float, threshold: float = 0.05) -> str:
    cell = f"{value:.3f}"
    if abs(value - expected) >= threshold:
        return rf"\textbf{{{cell}}}"
    return cell


def write_bias_table(rows: list[dict], out_path: Path) -> None:
    lines: list[str] = []
    lines.append(r"\begin{tabular}{llccc}")
    lines.append(r"\toprule")
    lines.append(r"Country & Target & Below q10 & Within 80\% band & Above q90 \\")
    lines.append(r"\textit{(expected)} &  & \textit{0.100} & \textit{0.800} & \textit{0.100} \\")
    lines.append(r"\midrule")

    current_country: str | None = None
    for i, row in enumerate(rows):
        country = row["country"]
        country_cell = ""
        if country != current_country:
            if current_country is not None:
                lines.append(r"\midrule")
            n_remaining = sum(1 for r in rows[i:] if r["country"] == country)
            country_cell = rf"\multirow{{{n_remaining}}}{{*}}{{{COUNTRY_DISPLAY[country]}}}"
            current_country = country

        cells = [
            country_cell,
            TARGET_DISPLAY[row["target"]],
            _format_bias(row["below_q10"], 0.1),
            _format_bias(row["within"], 0.8),
            _format_bias(row["above_q90"], 0.1),
        ]
        lines.append(" & ".join(cells) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")

    out_path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote %s", out_path)


def write_macros(
    pooled: dict[str, float | None], rows: list[dict], out_path: Path,
) -> None:
    """LaTeX \\newcommand macros for inline use in the paper body."""

    def _cmd(name: str, value: float | None, digits: int = 3) -> str:
        if value is None:
            return rf"\newcommand{{\{name}}}{{--}}"
        return rf"\newcommand{{\{name}}}{{{value:.{digits}f}}}"

    def _pct(name: str, value: float | None, nominal: float) -> str:
        """Gap in percentage points (negative = under-coverage)."""
        if value is None:
            return rf"\newcommand{{\{name}}}{{--}}"
        gap_pp = (value - nominal) * 100
        sign = "+" if gap_pp >= 0 else ""
        return rf"\newcommand{{\{name}}}{{{sign}{gap_pp:.1f}}}"

    lines: list[str] = []
    lines.append(r"% Auto-generated by src/coverage_tables.py")
    lines.append(_cmd("pooledFT80", pooled["ft80"]))
    lines.append(_cmd("pooledZS80", pooled["zs80"]))
    lines.append(_cmd("pooledFT50", pooled["ft50"]))
    lines.append(_cmd("pooledZS50", pooled["zs50"]))
    lines.append(_pct("pooledFT80Gap", pooled["ft80"], 0.8))
    lines.append(_pct("pooledZS80Gap", pooled["zs80"], 0.8))
    lines.append(_pct("pooledFT50Gap", pooled["ft50"], 0.5))
    lines.append(_pct("pooledZS50Gap", pooled["zs50"], 0.5))
    # Calibrated values — only present when the coverage_calibrated dir
    # exists. When absent, these macros still appear so \\input{}ing
    # them from the paper doesn't error out, but expand to "--".
    lines.append(_cmd("pooledCal80", pooled.get("cal80")))
    lines.append(_cmd("pooledCal50", pooled.get("cal50")))
    lines.append(_pct("pooledCal80Gap", pooled.get("cal80"), 0.8))
    lines.append(_pct("pooledCal50Gap", pooled.get("cal50"), 0.5))

    # Flag the two most egregious directional biases for inline cite.
    worst_right = max(rows, key=lambda r: r.get("above_q90", 0) if "above_q90" in r else 0)
    worst_left = max(rows, key=lambda r: r.get("below_q10", 0) if "below_q10" in r else 0)
    if "above_q90" in worst_right:
        lines.append(rf"\newcommand{{\worstRightCountry}}{{{COUNTRY_DISPLAY[worst_right['country']]}}}")
        lines.append(rf"\newcommand{{\worstRightTarget}}{{{TARGET_DISPLAY[worst_right['target']].lower()}}}")
        lines.append(_cmd("worstRightFrac", worst_right["above_q90"]))
    if "below_q10" in worst_left:
        lines.append(rf"\newcommand{{\worstLeftCountry}}{{{COUNTRY_DISPLAY[worst_left['country']]}}}")
        lines.append(rf"\newcommand{{\worstLeftTarget}}{{{TARGET_DISPLAY[worst_left['target']].lower()}}}")
        lines.append(_cmd("worstLeftFrac", worst_left["below_q10"]))

    out_path.write_text("\n".join(lines) + "\n")
    logger.info("Wrote %s", out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ft-dir", type=Path, default=DEFAULT_FT)
    parser.add_argument("--zs-dir", type=Path, default=DEFAULT_ZS)
    parser.add_argument("--cal-dir", type=Path, default=DEFAULT_CAL,
                        help="Optional; post-calibration test-era coverage dir")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    base = load_all(args.ft_dir)
    var = load_all(args.zs_dir)
    cal: pd.DataFrame | None = None
    if args.cal_dir.exists() and any(args.cal_dir.glob("*.parquet")):
        cal = load_all(args.cal_dir)
        logger.info("Loaded %d Cal rows (post-calibration test era)", len(cal))
    else:
        logger.info("No calibrated backtest at %s; tables omit Cal column",
                    args.cal_dir)
    logger.info("Loaded %d FT rows, %d ZS rows", len(base), len(var))

    args.output_dir.mkdir(parents=True, exist_ok=True)

    calib_rows, pooled = _build_calibration_rows(base, var, cal)
    write_calibration_table(
        calib_rows, pooled,
        args.output_dir / "tab_calibration.tex",
        include_cal=cal is not None,
    )

    bias_rows = _build_bias_rows(var)
    write_bias_table(bias_rows, args.output_dir / "tab_calibration_bias.tex")

    write_macros(pooled, bias_rows,
                 args.output_dir / "tab_calibration_macros.tex")

    # Pretty-print to stdout for quick review.
    print()
    print("Calibration table (pooled):")
    print(f"  FT  80%: {pooled['ft80']:.3f}  (nominal 0.800)")
    print(f"  ZS  80%: {pooled['zs80']:.3f}  (nominal 0.800)")
    if pooled.get("cal80") is not None:
        print(f"  Cal 80%: {pooled['cal80']:.3f}  (nominal 0.800)")
    print(f"  FT  50%: {pooled['ft50']:.3f}  (nominal 0.500)")
    print(f"  ZS  50%: {pooled['zs50']:.3f}  (nominal 0.500)")
    if pooled.get("cal50") is not None:
        print(f"  Cal 50%: {pooled['cal50']:.3f}  (nominal 0.500)")
    print()
    print("Directional bias (ZS):")
    for r in bias_rows:
        print(f"  {COUNTRY_DISPLAY[r['country']]:>8s}  {r['target']:<24s}  "
              f"below={r['below_q10']:.3f}  within={r['within']:.3f}  "
              f"above={r['above_q90']:.3f}  n={r['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
