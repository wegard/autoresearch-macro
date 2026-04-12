"""Leave-one-component-out ablation for each country's best config.

Per REVISION-PLAN-4 §8.2: for the final best configuration in each country,
remove one component at a time (each selected covariate, context truncation,
fine-tuning) and measure the full-eval MASE degradation.

Usage:
    HF_HUB_OFFLINE=1 uv run python scripts/run_leave_one_out_ablation.py
    HF_HUB_OFFLINE=1 uv run python scripts/run_leave_one_out_ablation.py --country sweden
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluate import evaluate
from prepare import MacroPanel
from train import apply_config_overrides, run

logger = logging.getLogger(__name__)

RESULTS_DIR = PROJECT_ROOT / "results"
CONFIGS_DIR = PROJECT_ROOT / "configs"

BEST_CONFIGS: dict[str, dict] = {
    "norway": {
        "state_file": "norway/search_state_llm_42.json",
    },
    "canada": {
        "state_file": "canada/search_state_llm_42.json",
    },
    "sweden": {
        "state_file": "sweden/search_state_llm_fixedgate_42.json",
    },
}


def load_panel(country: str) -> MacroPanel:
    if country == "norway":
        from prepare import load_panel
        return load_panel()
    elif country == "canada":
        from prepare_canada import load_panel_canada
        return load_panel_canada()
    elif country == "sweden":
        from prepare_sweden import load_panel_sweden
        return load_panel_sweden()
    raise ValueError(f"Unknown country: {country}")


def get_best_config(country: str) -> tuple[dict, float]:
    state_path = RESULTS_DIR / BEST_CONFIGS[country]["state_file"]
    state = json.loads(state_path.read_text())
    return state["best_config"], state["best_score"]


def generate_ablation_variants(config: dict) -> list[tuple[str, dict]]:
    """Generate leave-one-out variants from the best config."""
    variants: list[tuple[str, dict]] = []

    covs = config.get("covariates", [])
    for cov in covs:
        v = copy.deepcopy(config)
        v["covariates"] = [c for c in covs if c != cov]
        if cov in v.get("transforms", {}):
            del v["transforms"][cov]
        variants.append((f"drop_{cov}", v))

    if config.get("context_length") is not None:
        v = copy.deepcopy(config)
        v["context_length"] = None
        variants.append(("drop_context_length", v))

    if config.get("fine_tune", False):
        v = copy.deepcopy(config)
        v["fine_tune"] = False
        variants.append(("drop_fine_tune", v))

    if covs:
        v = copy.deepcopy(config)
        v["covariates"] = []
        v["transforms"] = {}
        variants.append(("drop_all_covariates", v))

    return variants


def eval_config(config: dict, country: str, panel: MacroPanel) -> float | None:
    """Run a config through the full validation pipeline and return avg MASE."""
    import tempfile

    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=CONFIGS_DIR, prefix="ablation_")
    config_path = Path(tmp)
    try:
        with open(fd, "w") as f:
            json.dump(config, f, indent=2)
        apply_config_overrides(str(config_path))
        fr = run(panel, era="validation", max_origins=None)
        eval_result = evaluate(fr, panel)
        if not eval_result.summary:
            return None
        scores = [
            eval_result.summary[h].get("avg_mase", float("inf"))
            for h in eval_result.summary
        ]
        return float(sum(scores) / len(scores)) if scores else None
    except Exception as e:
        logger.exception("Eval failed: %s", e)
        return None
    finally:
        config_path.unlink(missing_ok=True)


def run_ablation(country: str) -> dict:
    """Run all ablation variants for a country. Returns results dict."""
    logger.info("=" * 60)
    logger.info("ABLATION: %s", country.upper())
    logger.info("=" * 60)

    best_config, best_score = get_best_config(country)
    logger.info("Best config score: %.4f", best_score)
    logger.info("Best config: %s", json.dumps(best_config, indent=2))

    panel = load_panel(country)
    variants = generate_ablation_variants(best_config)
    logger.info("Generated %d ablation variants", len(variants))

    results = {
        "country": country,
        "best_config": best_config,
        "best_score": best_score,
        "ablations": [],
    }

    # First, re-run the best config to get the reference score
    logger.info("\nRunning FULL config (reference)...")
    t0 = time.time()
    ref_score = eval_config(best_config, country, panel)
    elapsed = time.time() - t0
    logger.info("  Reference score: %.4f (%.0fs)", ref_score or 0, elapsed)
    results["reference_score"] = ref_score

    for name, variant in variants:
        logger.info("\nRunning variant: %s ...", name)
        t0 = time.time()
        score = eval_config(variant, country, panel)
        elapsed = time.time() - t0
        degradation = None
        if score is not None and ref_score is not None:
            degradation = (score - ref_score) / ref_score * 100
        logger.info("  Score: %.4f  degradation: %+.2f%%  (%.0fs)",
                     score or 0, degradation or 0, elapsed)
        results["ablations"].append({
            "name": name,
            "config": variant,
            "score": score,
            "degradation_pct": degradation,
            "runtime_seconds": elapsed,
        })

    return results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Leave-one-out ablation")
    parser.add_argument(
        "--country", type=str, default=None,
        choices=["norway", "canada", "sweden"],
        help="Run ablation for a single country (default: all)",
    )
    args = parser.parse_args()

    countries = [args.country] if args.country else ["norway", "canada", "sweden"]
    all_results = {}

    for country in countries:
        results = run_ablation(country)
        all_results[country] = results

        # Save per-country results
        out_dir = RESULTS_DIR / country
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "ablation_leave_one_out.json"
        out_path.write_text(json.dumps(results, indent=2, default=str))
        logger.info("Saved %s ablation to %s", country, out_path)

    # Print summary table
    print("\n" + "=" * 80)
    print("LEAVE-ONE-OUT ABLATION SUMMARY")
    print("=" * 80)

    for country, results in all_results.items():
        ref = results.get("reference_score")
        print(f"\n--- {country.upper()} (reference: {ref:.4f}) ---")
        print(f"{'Variant':<30} {'MASE':>8} {'Degradation':>12}")
        print("-" * 52)
        print(f"{'FULL (reference)':<30} {ref:>8.4f} {'—':>12}")
        for abl in results["ablations"]:
            score = abl["score"]
            deg = abl["degradation_pct"]
            if score is not None:
                print(f"{abl['name']:<30} {score:>8.4f} {deg:>+11.2f}%")
            else:
                print(f"{abl['name']:<30} {'FAILED':>8} {'—':>12}")


if __name__ == "__main__":
    main()
