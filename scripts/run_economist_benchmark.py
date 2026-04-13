"""Run the manual economist benchmark for a given country.

Loads the hand-specified Chronos-2 config from
configs/manual_economist_benchmarks.yaml and evaluates it.

Usage:
    uv run python scripts/run_economist_benchmark.py --country norway --era validation
    uv run python scripts/run_economist_benchmark.py --country canada --era test --save
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logger = logging.getLogger(__name__)

CONFIGS_DIR = PROJECT_ROOT / "configs"
BENCHMARK_PATH = CONFIGS_DIR / "manual_economist_benchmarks.yaml"


def load_benchmark_config(country: str) -> dict:
    """Load the benchmark config for a country."""
    with open(BENCHMARK_PATH) as f:
        all_configs = yaml.safe_load(f)
    if country not in all_configs:
        raise ValueError(f"No benchmark config for {country}")
    config = all_configs[country]
    # Remove non-model fields
    config.pop("rationale", None)
    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run manual economist benchmark")
    parser.add_argument("--country", required=True, choices=["norway", "canada", "sweden"])
    parser.add_argument("--era", default="validation", choices=["validation", "test"])
    parser.add_argument("--save", action="store_true", help="Save results")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from baselines import load_country_panel
    from evaluate import evaluate, format_results_table, save_result
    from train import apply_config_overrides, run

    # Load benchmark config
    config = load_benchmark_config(args.country)
    logger.info("Benchmark config for %s: %s", args.country, json.dumps(config, default=str))

    # Write config to temp file and apply
    config_path = CONFIGS_DIR / "current_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    apply_config_overrides(str(config_path))

    # Load panel and run
    panel = load_country_panel(args.country)
    fr = run(panel, era=args.era)
    fr.method_name = "chronos2_manual"
    fr.country = args.country
    fr.config = {"benchmark": config, "country": args.country}

    eval_result = evaluate(fr, panel)
    print(format_results_table(eval_result))

    if args.save:
        save_result(fr, eval_result)
        logger.info("Results saved")

    # Cleanup
    if config_path.exists():
        config_path.unlink()


if __name__ == "__main__":
    main()
