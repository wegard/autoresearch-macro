"""Isotonic / conformal recalibration of Chronos-2 predictive quantiles.

The coverage backtest (src/coverage_backtest.py) established that
Chronos-2's native predictive bands systematically under-cover macro
time series: the nominal 80% band contains only ~70% of realisations,
and several target-country pairs show pronounced directional bias
(Canada retail sales: 42% of actuals fall above the 90th percentile).
Because the miscalibration survives zero-shot mode, it is a property
of the foundation model itself — not the LoRA fine-tune. See the
project_coverage_followups memory for the full diagnosis.

This module fits a per-(country, target, horizon) isotonic calibrator
on the VALIDATION era and serialises it so prediction-time code
(src/live_forecast.py, src/coverage_backtest.py --apply-calibration)
can adjust Chronos-2's quantile outputs before they reach the
dashboard.

Method: for each series, collect the PIT values of validation-era
actuals under the base-model predictive distribution. Let F̂ denote
their empirical CDF. To emit a calibrated τ-quantile at prediction
time, substitute τ' = F̂⁻¹(τ) into the base quantile function. This
is the standard isotonic recalibration used in the conformal-
prediction literature (Romano et al. 2019; Kuleshov et al. 2018).

The calibrator JSON is small (~40 KB total for 3 countries × 4
targets × 12 horizons × 5 τ levels) and deterministic given the
validation-era backtest parquet files.

Usage:
  uv run python src/calibration.py fit     # fit from coverage_validation/
  uv run python src/calibration.py inspect # pretty-print summary
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
VALIDATION_DIR = RESULTS_DIR / "coverage_validation"
CALIBRATION_DIR = RESULTS_DIR / "calibration"
CALIBRATOR_PATH = CALIBRATION_DIR / "calibrator.json"

# Quantile levels emitted by coverage_backtest / live_forecast. Must
# match live_forecast.QUANTILE_LEVELS exactly — the calibrator only
# knows how to interpolate between these knots.
QUANTILE_LEVELS: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)

# How many validation PIT values we require before trusting a per-
# series calibrator. Below this, fall back to identity (no change).
MIN_VALIDATION_OBS = 30


# ---------------------------------------------------------------------------
# PIT estimation
# ---------------------------------------------------------------------------


def _pit_linear_interp(
    actual: np.ndarray,
    q_values: np.ndarray,
) -> np.ndarray:
    """Piecewise-linear PIT for actuals under the 5-quantile CDF.

    q_values is shape (n, 5) with columns aligned to QUANTILE_LEVELS
    in the order (q10, q25, q50, q75, q90). For each actual:

      * actual <= q10       →  linearly extrapolate into [0, 0.1]
                               using the q10→q25 local density
      * q10 < actual <= q25 →  PIT ∈ [0.1, 0.25] by linear interp
      * q25 < actual <= q50 →  PIT ∈ [0.25, 0.5]
      * q50 < actual <= q75 →  PIT ∈ [0.5, 0.75]
      * q75 < actual <= q90 →  PIT ∈ [0.75, 0.9]
      * actual  >  q90      →  linearly extrapolate into [0.9, 1]
                               using the q75→q90 local density

    PIT values are clipped to [1e-4, 1-1e-4] to avoid zero-variance
    edge cases in downstream empirical-CDF inversion.
    """
    q10, q25, q50, q75, q90 = (q_values[:, i] for i in range(5))
    # Small epsilon protects against duplicate knot values (flat CDF);
    # near-collisions do happen on integer-valued series like
    # unemployment rates.
    eps = 1e-9
    pit = np.empty_like(actual, dtype=float)

    below = actual <= q10
    above = actual > q90
    b1 = (~below) & (actual <= q25)
    b2 = (actual > q25) & (actual <= q50)
    b3 = (actual > q50) & (actual <= q75)
    b4 = (actual > q75) & (~above)

    # Lower extrapolation: extend the q10→q25 line leftward.
    slope_lower = (0.25 - 0.1) / np.maximum(q25 - q10, eps)
    pit[below] = 0.1 - (q10[below] - actual[below]) * slope_lower[below]

    pit[b1] = 0.1 + 0.15 * (actual[b1] - q10[b1]) / np.maximum(q25[b1] - q10[b1], eps)
    pit[b2] = 0.25 + 0.25 * (actual[b2] - q25[b2]) / np.maximum(q50[b2] - q25[b2], eps)
    pit[b3] = 0.5 + 0.25 * (actual[b3] - q50[b3]) / np.maximum(q75[b3] - q50[b3], eps)
    pit[b4] = 0.75 + 0.15 * (actual[b4] - q75[b4]) / np.maximum(q90[b4] - q75[b4], eps)

    # Upper extrapolation: extend the q75→q90 line rightward.
    slope_upper = (0.9 - 0.75) / np.maximum(q90 - q75, eps)
    pit[above] = 0.9 + (actual[above] - q90[above]) * slope_upper[above]

    return np.clip(pit, 1e-4, 1 - 1e-4)


# ---------------------------------------------------------------------------
# Calibrator fitting
# ---------------------------------------------------------------------------


def fit_calibrator_from_dir(validation_dir: Path) -> dict[str, Any]:
    """Load validation-era per-country parquet files and fit the
    calibrator.

    Returns a nested dict ready for JSON serialisation:

        {
          "version": 1,
          "quantile_levels": [0.1, 0.25, 0.5, 0.75, 0.9],
          "min_validation_obs": 30,
          "series": {
            "<country>": {
              "<target>": {
                "<horizon>": {
                  "n_validation": 120,
                  "tau_prime": [0.045, 0.18, 0.48, 0.74, 0.88]
                  # ^ F̂⁻¹(τ) for τ ∈ quantile_levels
                }
              }
            }
          }
        }
    """
    frames: list[pd.DataFrame] = []
    for path in sorted(validation_dir.glob("*.parquet")):
        frames.append(pd.read_parquet(path))
    if not frames:
        raise FileNotFoundError(
            f"No per-country parquet files under {validation_dir}. "
            "Run: uv run python src/coverage_backtest.py --era validation"
        )
    df = pd.concat(frames, ignore_index=True)
    logger.info("Loaded %d validation rows from %s", len(df), validation_dir)

    calibrator: dict[str, Any] = {
        "version": 1,
        "quantile_levels": list(QUANTILE_LEVELS),
        "min_validation_obs": MIN_VALIDATION_OBS,
        "series": {},
    }

    required_cols = ["country", "target", "horizon", "actual",
                     "q10", "q25", "q50", "q75", "q90"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Validation parquet missing columns: {missing}")

    for (country, target, horizon), group in df.groupby(
        ["country", "target", "horizon"],
    ):
        actual = group["actual"].to_numpy(dtype=float)
        q_values = group[["q10", "q25", "q50", "q75", "q90"]].to_numpy(
            dtype=float,
        )

        # Drop rows with any NaN in actual or quantiles — treat them as
        # missing observations rather than letting them pollute the
        # empirical CDF.
        mask = ~(np.isnan(actual) | np.isnan(q_values).any(axis=1))
        actual = actual[mask]
        q_values = q_values[mask]

        if len(actual) < MIN_VALIDATION_OBS:
            logger.warning(
                "Insufficient validation obs for %s/%s/h=%d (%d < %d); "
                "calibrator will pass through unchanged.",
                country, target, int(horizon), len(actual), MIN_VALIDATION_OBS,
            )
            continue

        pits = _pit_linear_interp(actual, q_values)
        tau_prime = [float(np.quantile(pits, tau)) for tau in QUANTILE_LEVELS]

        calibrator["series"].setdefault(country, {}) \
            .setdefault(target, {})[str(int(horizon))] = {
                "n_validation": int(len(actual)),
                "tau_prime": tau_prime,
            }

    return calibrator


# ---------------------------------------------------------------------------
# Applying the calibrator at prediction time
# ---------------------------------------------------------------------------


def _interpolate_base_quantile(
    base_quantiles: np.ndarray, tau: float,
) -> float:
    """Linearly interpolate the base model's quantile function
    `Q(τ)` defined by knots at QUANTILE_LEVELS.

    `base_quantiles` has shape (5,) with values at (q10, q25, q50,
    q75, q90). For τ outside [0.1, 0.9] we extrapolate using the
    adjacent slope so recalibration can widen the band beyond the
    outermost knots.
    """
    levels = np.asarray(QUANTILE_LEVELS, dtype=float)
    eps = 1e-9
    if tau <= levels[0]:
        # Extrapolate left: extend slope between levels[0] and levels[1]
        slope = (base_quantiles[1] - base_quantiles[0]) / max(levels[1] - levels[0], eps)
        return float(base_quantiles[0] - (levels[0] - tau) * slope)
    if tau >= levels[-1]:
        slope = (base_quantiles[-1] - base_quantiles[-2]) / max(levels[-1] - levels[-2], eps)
        return float(base_quantiles[-1] + (tau - levels[-1]) * slope)
    # Interior: standard linear interp
    return float(np.interp(tau, levels, base_quantiles))


def apply_calibrator(
    base_quantiles: dict[float, float] | dict[str, float],
    country: str,
    target: str,
    horizon: int,
    calibrator: dict[str, Any],
) -> dict[float, float]:
    """Given a base-model quantile dict (τ → value), return a
    calibrated dict with the same keys.

    Falls back to the identity map when the calibrator has no entry
    for the requested series (e.g., too few validation observations).

    Accepts either float or string τ keys in `base_quantiles`; output
    keys are always float.
    """
    # Normalise input keys.
    base: dict[float, float] = {float(k): float(v) for k, v in base_quantiles.items()}
    missing_levels = [tau for tau in QUANTILE_LEVELS if tau not in base]
    if missing_levels:
        raise KeyError(
            f"base_quantiles missing levels {missing_levels}; need {list(QUANTILE_LEVELS)}"
        )

    series_entry = (
        calibrator.get("series", {})
        .get(country, {})
        .get(target, {})
        .get(str(int(horizon)))
    )
    if series_entry is None:
        return base  # identity fallback
    tau_prime = series_entry.get("tau_prime")
    if not tau_prime or len(tau_prime) != len(QUANTILE_LEVELS):
        return base

    base_array = np.array([base[tau] for tau in QUANTILE_LEVELS], dtype=float)
    recalibrated: dict[float, float] = {}
    for nominal_tau, tp in zip(QUANTILE_LEVELS, tau_prime, strict=True):
        recalibrated[nominal_tau] = _interpolate_base_quantile(base_array, tp)

    # Enforce monotonicity (isotonic): recalibrated quantiles should be
    # non-decreasing in τ. If numerical interpolation produced a
    # crossing — can happen for very narrow base bands — sort in place.
    keys = sorted(recalibrated.keys())
    values = [recalibrated[k] for k in keys]
    values = list(np.maximum.accumulate(values))
    return dict(zip(keys, values, strict=True))


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def save_calibrator(calibrator: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(calibrator, indent=2, default=str))
    logger.info("Wrote %s", path)


def load_calibrator(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"No calibrator at {path}. Run: uv run python src/calibration.py fit"
        )
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_fit(args: argparse.Namespace) -> int:
    calibrator = fit_calibrator_from_dir(args.validation_dir)
    save_calibrator(calibrator, args.output)
    _print_summary(calibrator)
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    calibrator = load_calibrator(args.path)
    _print_summary(calibrator)
    return 0


def _print_summary(calibrator: dict[str, Any]) -> None:
    print(f"Calibrator version {calibrator.get('version')}")
    print(f"Quantile levels: {calibrator.get('quantile_levels')}")
    print("Series with fitted calibrators:")
    series = calibrator.get("series", {})
    for country in sorted(series):
        for target in sorted(series[country]):
            horizons = series[country][target]
            for h in sorted(horizons, key=int):
                entry = horizons[h]
                tp = entry["tau_prime"]
                print(
                    f"  {country:>8s}/{target:<24s}/h={h:>2s}  "
                    f"n={entry['n_validation']:>3d}  "
                    f"τ' = [{', '.join(f'{x:.3f}' for x in tp)}]"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fit = sub.add_parser("fit", help="Fit calibrator from validation-era backtest")
    p_fit.add_argument("--validation-dir", type=Path, default=VALIDATION_DIR)
    p_fit.add_argument("--output", type=Path, default=CALIBRATOR_PATH)
    p_fit.set_defaults(func=_cmd_fit)

    p_inspect = sub.add_parser("inspect", help="Print summary of an existing calibrator")
    p_inspect.add_argument("--path", type=Path, default=CALIBRATOR_PATH)
    p_inspect.set_defaults(func=_cmd_inspect)

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
