"""Ablation analysis: trace the search trajectory on the test era.

Runs each accepted search configuration on the test era to identify
which component of the pipeline drives the overfitting.

Usage:
    uv run python scripts/ablation_analysis.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from evaluate import ForecastResult, evaluate, format_results_table, save_result
from prepare import load_panel

logger = logging.getLogger(__name__)

# Ablation configs: trace the search trajectory step by step
ABLATION_CONFIGS = [
    {
        "name": "zs_baseline",
        "label": "Zero-shot baseline",
        "config": {
            "covariates": [],
            "transforms": {},
            "context_length": None,
            "fine_tune": False,
            "fine_tune_steps": 1000,
            "fine_tune_lr": 1e-5,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
    {
        "name": "ctx96",
        "label": "+ context_length=96",
        "config": {
            "covariates": [],
            "transforms": {},
            "context_length": 96,
            "fine_tune": False,
            "fine_tune_steps": 1000,
            "fine_tune_lr": 1e-5,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
    {
        "name": "ctx96_brent",
        "label": "+ brent_crude",
        "config": {
            "covariates": ["brent_crude"],
            "transforms": {},
            "context_length": 96,
            "fine_tune": False,
            "fine_tune_steps": 1000,
            "fine_tune_lr": 1e-5,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
    {
        "name": "ctx96_brent_policy",
        "label": "+ policy_rate",
        "config": {
            "covariates": ["brent_crude", "policy_rate"],
            "transforms": {},
            "context_length": 96,
            "fine_tune": False,
            "fine_tune_steps": 1000,
            "fine_tune_lr": 1e-5,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
    {
        "name": "ctx96_3covs",
        "label": "+ us_cpi",
        "config": {
            "covariates": ["brent_crude", "policy_rate", "us_cpi"],
            "transforms": {},
            "context_length": 96,
            "fine_tune": False,
            "fine_tune_steps": 1000,
            "fine_tune_lr": 1e-5,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
    {
        "name": "ctx96_4covs",
        "label": "+ nok_eur",
        "config": {
            "covariates": ["brent_crude", "policy_rate", "us_cpi", "nok_eur"],
            "transforms": {},
            "context_length": 96,
            "fine_tune": False,
            "fine_tune_steps": 1000,
            "fine_tune_lr": 1e-5,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
    {
        "name": "ctx96_4covs_ft",
        "label": "+ LoRA fine-tune",
        "config": {
            "covariates": ["brent_crude", "policy_rate", "us_cpi", "nok_eur"],
            "transforms": {},
            "context_length": 96,
            "fine_tune": True,
            "fine_tune_steps": 100,
            "fine_tune_lr": 5e-6,
            "grouping": "univariate",
            "num_samples": 20,
        },
    },
]


def run_ablation_config(config: dict, panel, era: str = "test") -> float | None:
    """Run a single ablation config and return the avg MASE."""
    from train import apply_config_overrides, run

    # Write config to temp file
    config_path = Path("configs/ablation_temp.json")
    config_path.write_text(json.dumps(config))
    apply_config_overrides(str(config_path))

    try:
        fr = run(panel, era=era, max_origins=None)
        eval_result = evaluate(fr, panel)

        if not eval_result.summary:
            return None

        scores = [
            eval_result.summary[h].get("avg_mase", float("inf"))
            for h in eval_result.summary
        ]
        return float(sum(scores) / len(scores)) if scores else None
    except Exception as e:
        logger.exception("Ablation run failed: %s", e)
        return None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    panel = load_panel()

    print(f"\n{'=' * 70}")
    print(f"  ABLATION ANALYSIS — Test Era (2016+)")
    print(f"{'=' * 70}\n")

    results = []
    for ablation in ABLATION_CONFIGS:
        name = ablation["name"]
        label = ablation["label"]
        config = ablation["config"]

        logger.info("Running ablation: %s", label)
        start = time.time()
        score = run_ablation_config(config, panel, era="test")
        elapsed = time.time() - start

        result = {
            "name": name,
            "label": label,
            "mase": score,
            "runtime": elapsed,
        }
        results.append(result)

        score_str = f"{score:.4f}" if score else "FAILED"
        print(f"  {label:30s}  MASE = {score_str}  ({elapsed:.0f}s)")

    # Also run on validation era for comparison
    print(f"\n{'=' * 70}")
    print(f"  ABLATION ANALYSIS — Validation Era (2006-2015)")
    print(f"{'=' * 70}\n")

    val_results = []
    for ablation in ABLATION_CONFIGS:
        name = ablation["name"]
        label = ablation["label"]
        config = ablation["config"]

        logger.info("Running ablation (validation): %s", label)
        start = time.time()
        score = run_ablation_config(config, panel, era="validation")
        elapsed = time.time() - start

        val_result = {
            "name": name,
            "label": label,
            "mase": score,
            "runtime": elapsed,
        }
        val_results.append(val_result)

        score_str = f"{score:.4f}" if score else "FAILED"
        print(f"  {label:30s}  MASE = {score_str}  ({elapsed:.0f}s)")

    # Print comparison table
    print(f"\n{'=' * 70}")
    print(f"  COMPARISON: Validation vs Test")
    print(f"{'=' * 70}\n")
    print(f"  {'Config':30s}  {'Validation':>12s}  {'Test':>12s}  {'Delta':>10s}")
    print(f"  {'-' * 70}")
    for vr, tr in zip(val_results, results):
        v = f"{vr['mase']:.4f}" if vr['mase'] else "—"
        t = f"{tr['mase']:.4f}" if tr['mase'] else "—"
        if vr['mase'] and tr['mase']:
            delta = f"{(tr['mase'] / vr['mase'] - 1) * 100:+.1f}%"
        else:
            delta = "—"
        print(f"  {vr['label']:30s}  {v:>12s}  {t:>12s}  {delta:>10s}")

    # Save results
    output = {
        "validation": val_results,
        "test": results,
    }
    output_path = Path("results/ablation_results.json")
    output_path.write_text(json.dumps(output, indent=2))
    logger.info("Saved ablation results to %s", output_path)

    # Cleanup
    temp = Path("configs/ablation_temp.json")
    if temp.exists():
        temp.unlink()


if __name__ == "__main__":
    main()
