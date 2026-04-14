"""Tests for src/calibration.py — isotonic recalibration primitives."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from calibration import (
    MIN_VALIDATION_OBS,
    QUANTILE_LEVELS,
    _interpolate_base_quantile,
    _pit_linear_interp,
    apply_calibrator,
    fit_calibrator_from_dir,
    load_calibrator,
    save_calibrator,
)


def _synthetic_validation_frame(
    country: str = "norway",
    target: str = "cpi",
    horizon: int = 1,
    n_origins: int = 120,
    width_factor: float = 1.0,
    bias: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Fabricate a validation-era parquet-shape frame.

    Actuals are drawn from a Gaussian; quantiles are placed at the
    correct theoretical positions scaled by `width_factor` (< 1 =
    model bands too narrow → calibrator should widen) and shifted
    by `bias` (so actuals are systematically above the model's median).
    """
    rng = np.random.default_rng(seed)
    actual = rng.normal(loc=0.0, scale=1.0, size=n_origins) + bias
    # Model puts q10..q90 at scaled Gaussian quantiles around zero.
    theoretical = np.array([-1.281, -0.674, 0.0, 0.674, 1.281])
    quantiles = theoretical * width_factor
    rows = [
        {
            "country": country, "target": target, "horizon": horizon,
            "origin": f"2006-{(i % 12) + 1:02d}-01",
            "actual": float(a),
            "q10": quantiles[0], "q25": quantiles[1], "q50": quantiles[2],
            "q75": quantiles[3], "q90": quantiles[4], "mean": quantiles[2],
        }
        for i, a in enumerate(actual)
    ]
    return pd.DataFrame(rows)


class TestPitInterpolation:
    def test_pit_exactly_at_knots(self) -> None:
        q = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]])
        for actual_val, expected in [(1.0, 0.1), (2.0, 0.25), (3.0, 0.5),
                                     (4.0, 0.75), (5.0, 0.9)]:
            pit = _pit_linear_interp(np.array([actual_val]), q)[0]
            assert abs(pit - expected) < 1e-6, f"actual={actual_val}: pit={pit}, expected {expected}"

    def test_pit_midway_between_knots(self) -> None:
        q = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]])
        # Midway between q50 and q75 should give PIT = 0.625
        pit = _pit_linear_interp(np.array([3.5]), q)[0]
        assert abs(pit - 0.625) < 1e-6

    def test_pit_clipped_to_open_unit_interval(self) -> None:
        q = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]])
        pit_low = _pit_linear_interp(np.array([-10.0]), q)[0]
        pit_high = _pit_linear_interp(np.array([100.0]), q)[0]
        assert 0.0 < pit_low < 0.001
        assert 1.0 > pit_high > 0.999


class TestInterpolateBaseQuantile:
    def test_at_knot(self) -> None:
        base = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _interpolate_base_quantile(base, 0.5) == 3.0
        assert _interpolate_base_quantile(base, 0.1) == 1.0

    def test_linear_interior(self) -> None:
        base = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        # At τ = 0.375 (midway between q25 and q50) value should be 2.5
        assert abs(_interpolate_base_quantile(base, 0.375) - 2.5) < 1e-9

    def test_extrapolate_below(self) -> None:
        base = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        # q10 = 1.0 with local slope (2-1)/(0.25-0.1) = 6.67
        # τ = 0.05 is 0.05 below q10 level
        val = _interpolate_base_quantile(base, 0.05)
        assert val < 1.0
        assert abs(val - (1.0 - 0.05 * (1.0 / 0.15))) < 1e-6

    def test_extrapolate_above(self) -> None:
        base = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val = _interpolate_base_quantile(base, 0.95)
        assert val > 5.0


class TestApplyCalibrator:
    def test_identity_roundtrip(self) -> None:
        calibrator = {
            "series": {
                "norway": {
                    "cpi": {
                        "1": {"n_validation": 100, "tau_prime": list(QUANTILE_LEVELS)},
                    },
                },
            },
        }
        base = {0.1: 1.0, 0.25: 2.0, 0.5: 3.0, 0.75: 4.0, 0.9: 5.0}
        out = apply_calibrator(base, "norway", "cpi", 1, calibrator)
        for tau, value in base.items():
            assert abs(out[tau] - value) < 1e-9

    def test_widening_calibrator(self) -> None:
        """If tau_prime spans a wider range than QUANTILE_LEVELS, the
        calibrated quantiles should be wider than the base."""
        calibrator = {
            "series": {
                "norway": {
                    "cpi": {
                        "1": {
                            "n_validation": 100,
                            "tau_prime": [0.05, 0.2, 0.5, 0.8, 0.95],
                        },
                    },
                },
            },
        }
        base = {0.1: 1.0, 0.25: 2.0, 0.5: 3.0, 0.75: 4.0, 0.9: 5.0}
        out = apply_calibrator(base, "norway", "cpi", 1, calibrator)
        assert out[0.1] < base[0.1]  # wider on left
        assert out[0.9] > base[0.9]  # wider on right
        assert out[0.5] == 3.0       # median unchanged (symmetric)

    def test_shift_calibrator(self) -> None:
        """Asymmetric tau_prime should shift calibrated quantiles."""
        calibrator = {
            "series": {
                "norway": {
                    "cpi": {
                        "1": {
                            "n_validation": 100,
                            "tau_prime": [0.3, 0.45, 0.7, 0.85, 0.95],
                        },
                    },
                },
            },
        }
        base = {0.1: 1.0, 0.25: 2.0, 0.5: 3.0, 0.75: 4.0, 0.9: 5.0}
        out = apply_calibrator(base, "norway", "cpi", 1, calibrator)
        # Every calibrated quantile draws from a higher base level, so
        # all move up compared to the raw values.
        for tau in [0.1, 0.25, 0.5, 0.75, 0.9]:
            assert out[tau] > base[tau]

    def test_fallback_to_identity_when_series_missing(self) -> None:
        calibrator = {"series": {}}
        base = {0.1: 1.0, 0.25: 2.0, 0.5: 3.0, 0.75: 4.0, 0.9: 5.0}
        out = apply_calibrator(base, "mars", "cpi", 1, calibrator)
        assert out == base

    def test_monotonicity_enforced(self) -> None:
        """Even pathological tau_prime that would cause crossing must
        yield a monotone calibrated quantile function."""
        calibrator = {
            "series": {
                "norway": {
                    "cpi": {
                        "1": {
                            "n_validation": 100,
                            # Non-monotone on purpose — violates isotonic
                            # assumption; apply_calibrator must correct it.
                            "tau_prime": [0.5, 0.4, 0.3, 0.2, 0.1],
                        },
                    },
                },
            },
        }
        base = {0.1: 1.0, 0.25: 2.0, 0.5: 3.0, 0.75: 4.0, 0.9: 5.0}
        out = apply_calibrator(base, "norway", "cpi", 1, calibrator)
        values = [out[tau] for tau in sorted(out)]
        assert values == sorted(values), f"non-monotone: {values}"


class TestFitCalibratorFromDir:
    def test_round_trip(self, tmp_path: Path) -> None:
        df = _synthetic_validation_frame(n_origins=200, width_factor=1.0)
        df.to_parquet(tmp_path / "norway.parquet")
        cal = fit_calibrator_from_dir(tmp_path)
        assert cal["version"] == 1
        entry = cal["series"]["norway"]["cpi"]["1"]
        assert entry["n_validation"] == 200
        # With width_factor=1.0 the model is correctly calibrated, so
        # tau_prime should be close to the nominal QUANTILE_LEVELS.
        for tp, nominal in zip(entry["tau_prime"], QUANTILE_LEVELS, strict=True):
            assert abs(tp - nominal) < 0.1

    def test_save_and_load(self, tmp_path: Path) -> None:
        df = _synthetic_validation_frame(n_origins=100)
        df.to_parquet(tmp_path / "norway.parquet")
        cal = fit_calibrator_from_dir(tmp_path)
        path = tmp_path / "calibrator.json"
        save_calibrator(cal, path)
        loaded = load_calibrator(path)
        assert loaded == cal

    def test_insufficient_obs_falls_back(self, tmp_path: Path) -> None:
        df = _synthetic_validation_frame(n_origins=MIN_VALIDATION_OBS - 1)
        df.to_parquet(tmp_path / "norway.parquet")
        cal = fit_calibrator_from_dir(tmp_path)
        # Short series gets skipped entirely → no entry → apply falls
        # back to identity.
        assert "norway" not in cal.get("series", {}) or \
               "1" not in cal.get("series", {}).get("norway", {}).get("cpi", {})

    def test_fit_detects_too_narrow_bands(self, tmp_path: Path) -> None:
        """If the model under-covers (bands too narrow), tau_prime
        should spread wider than nominal levels."""
        df = _synthetic_validation_frame(n_origins=500, width_factor=0.5)
        df.to_parquet(tmp_path / "norway.parquet")
        cal = fit_calibrator_from_dir(tmp_path)
        tp = cal["series"]["norway"]["cpi"]["1"]["tau_prime"]
        # tau_prime for nominal 0.1 should be < 0.1 (more extreme),
        # tau_prime for nominal 0.9 should be > 0.9.
        assert tp[0] < 0.1
        assert tp[-1] > 0.9

    def test_missing_parquet_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            fit_calibrator_from_dir(tmp_path)


class TestEndToEndCalibration:
    """Sanity check: fit on under-covering synthetic data, then
    verify applying the calibrator to out-of-sample quantile-aligned
    actuals brings empirical coverage closer to nominal."""

    def test_calibration_reduces_undercoverage(self, tmp_path: Path) -> None:
        # Fit on training data where model bands are ~20% too narrow —
        # realistic for Chronos-2's observed miscalibration (~10 pp
        # gap). More extreme widths would test the limits of linear
        # extrapolation between just 5 quantile knots, which is not
        # what we're trying to exercise here.
        train = _synthetic_validation_frame(
            n_origins=500, width_factor=0.8, seed=1,
        )
        train.to_parquet(tmp_path / "norway.parquet")
        cal = fit_calibrator_from_dir(tmp_path)

        # Independent test-era draws from the same (miscalibrated) base.
        rng = np.random.default_rng(2)
        actual = rng.normal(0, 1, size=2000)
        theoretical = np.array([-1.281, -0.674, 0.0, 0.674, 1.281])
        q_base = theoretical * 0.8
        base_q = dict(zip(QUANTILE_LEVELS, q_base, strict=True))

        def _coverage(lo: float, hi: float) -> tuple[float, float]:
            raw = ((actual >= base_q[lo]) & (actual <= base_q[hi])).mean()
            cal_q = apply_calibrator(base_q, "norway", "cpi", 1, cal)
            cal_cov = ((actual >= cal_q[lo]) & (actual <= cal_q[hi])).mean()
            return float(raw), float(cal_cov)

        raw80, cal80 = _coverage(0.1, 0.9)
        raw50, cal50 = _coverage(0.25, 0.75)

        # Raw 80% band covers roughly Gaussian 80% at 0.8 spread.
        assert 0.6 <= raw80 <= 0.75
        # Calibrated must move toward nominal on both bands. With only
        # 5 quantile knots the linear tail-extrapolation has finite
        # reach, so we don't demand full recovery — production
        # Chronos-2 output has richer quantile structure.
        assert cal80 > raw80
        assert cal50 > raw50
        # Gap must shrink by at least 25%.
        assert (0.8 - cal80) < (0.8 - raw80) * 0.75, \
            f"cal80={cal80:.3f} did not shrink gap enough from raw80={raw80:.3f}"
