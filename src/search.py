"""Outer loop controller for the autoresearch-macro search.

Orchestrates an LLM-guided search over the forecasting pipeline configuration.
Uses Claude API to propose config changes, evaluates them via train.py,
and accepts/rejects based on validation performance.

Usage:
    python src/search.py                         # Run until interrupted
    python src/search.py --max-iterations 10     # Run 10 iterations
    python src/search.py --resume                # Resume from saved state
    python src/search.py --status                # Show current search state
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

RESULTS_DIR = PROJECT_ROOT / "results"
SEARCH_LOG_PATH = RESULTS_DIR / "search_log.jsonl"
SEARCH_STATE_PATH = RESULTS_DIR / "search_state.json"
CONFIG_DIR = PROJECT_ROOT / "configs"
CURRENT_CONFIG_PATH = CONFIG_DIR / "current_config.json"
PROGRAM_PATH = PROJECT_ROOT / "program.md"
SEARCH_SPACE_PATH = CONFIG_DIR / "search_space.yml"

# Subsampled origins for quick evaluation
QUICK_EVAL_ORIGINS = 20
# Score metric key in eval_result.summary
SCORE_METRIC = "avg_mase"


# ---------------------------------------------------------------------------
# Search state
# ---------------------------------------------------------------------------


@dataclass
class IterationRecord:
    """Record of a single search iteration."""

    iteration: int
    config: dict[str, Any]
    quick_score: float | None
    full_score: float | None
    status: str  # "accepted", "rejected", "error"
    description: str
    runtime_seconds: float
    timestamp: str


@dataclass
class SearchState:
    """Persistent state for the search loop."""

    iteration: int = 0
    best_score: float = float("inf")
    best_config: dict[str, Any] = field(default_factory=dict)
    baseline_score: float = float("inf")
    history: list[IterationRecord] = field(default_factory=list)
    start_time: str = ""

    def to_json(self) -> str:
        data = {
            "iteration": self.iteration,
            "best_score": self.best_score,
            "best_config": self.best_config,
            "baseline_score": self.baseline_score,
            "history": [asdict(h) for h in self.history],
            "start_time": self.start_time,
        }
        return json.dumps(data, indent=2, default=str)

    @classmethod
    def from_json(cls, text: str) -> SearchState:
        data = json.loads(text)
        state = cls(
            iteration=data["iteration"],
            best_score=data["best_score"],
            best_config=data["best_config"],
            baseline_score=data["baseline_score"],
            start_time=data.get("start_time", ""),
        )
        for h in data.get("history", []):
            state.history.append(IterationRecord(**h))
        return state

    def save(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        SEARCH_STATE_PATH.write_text(self.to_json())

    @classmethod
    def load(cls) -> SearchState | None:
        if SEARCH_STATE_PATH.exists():
            return cls.from_json(SEARCH_STATE_PATH.read_text())
        return None


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "covariates": [],
    "transforms": {},
    "context_length": None,
    "fine_tune": False,
    "fine_tune_steps": 1000,
    "fine_tune_lr": 1e-5,
    "grouping": "univariate",
    "num_samples": 20,
}


def write_config(config: dict[str, Any]) -> Path:
    """Write config to JSON file for train.py to read."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_CONFIG_PATH.write_text(json.dumps(config, indent=2))
    return CURRENT_CONFIG_PATH


def merge_config(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge override config into base config."""
    merged = base.copy()
    merged.update(overrides)
    return merged


# ---------------------------------------------------------------------------
# LLM-guided proposal
# ---------------------------------------------------------------------------


def build_prompt(
    state: SearchState,
    search_space: str,
    available_covariates: list[str],
    max_history: int = 15,
    program_override: str | None = None,
) -> tuple[str, str]:
    """Build system and user prompts for the Claude API call.

    Returns:
        (system_prompt, user_prompt) tuple.
    """
    # System prompt: program.md (or override)
    program_file = Path(program_override) if program_override else PROGRAM_PATH
    system_prompt = program_file.read_text()

    # User prompt: search space + state + history
    lines = [
        f"## Search space\n\n```yaml\n{search_space}\n```\n",
        f"## Available covariates\n\n{', '.join(available_covariates)}\n",
        f"## Current best\n\nConfig: ```json\n{json.dumps(state.best_config, indent=2)}\n```",
        f"Score (avg_mase): {state.best_score:.4f}",
        f"Baseline score: {state.baseline_score:.4f}\n",
    ]

    if state.history:
        lines.append("## Recent history\n")
        recent = state.history[-max_history:]
        for rec in recent:
            score_str = f"{rec.full_score:.4f}" if rec.full_score else f"~{rec.quick_score:.4f}"
            # Summarize config changes vs best
            cfg_summary = _summarize_config(rec.config)
            lines.append(
                f"- Iter {rec.iteration}: {cfg_summary} → {score_str} ({rec.status})"
            )
        lines.append("")

    lines.append(
        "Propose the next configuration to try. "
        "Return ONLY a JSON object with the fields you want to change."
    )

    return system_prompt, "\n".join(lines)


def _summarize_config(config: dict[str, Any]) -> str:
    """Create a short summary of a config for the history."""
    parts = []
    covs = config.get("covariates", [])
    if covs:
        parts.append(f"covs=[{','.join(covs[:3])}{'...' if len(covs) > 3 else ''}]")
    transforms = config.get("transforms", {})
    if transforms:
        parts.append(f"transforms={len(transforms)}")
    cl = config.get("context_length")
    if cl is not None:
        parts.append(f"ctx={cl}")
    if config.get("fine_tune"):
        parts.append("ft=true")
    return ", ".join(parts) if parts else "baseline"


def propose_config(
    state: SearchState,
    available_covariates: list[str],
    program_override: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Call Claude API to propose the next config.

    Returns:
        (proposed_config_overrides, description)
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment or .env")

    search_space = SEARCH_SPACE_PATH.read_text() if SEARCH_SPACE_PATH.exists() else ""
    system_prompt, user_prompt = build_prompt(
        state, search_space, available_covariates, program_override=program_override
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text
    logger.info("LLM response:\n%s", raw_text)

    # Parse JSON from response (handle markdown code blocks)
    config_overrides = _parse_json_response(raw_text)
    description = _extract_description(raw_text, config_overrides)

    return config_overrides, description


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try to find JSON in code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try the whole text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object anywhere in the text
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse JSON from LLM response, using empty config")
    return {}


def _extract_description(text: str, config: dict[str, Any]) -> str:
    """Extract a brief description from the LLM response."""
    # Use the config summary as fallback description
    return _summarize_config(config)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def run_and_evaluate(
    config: dict[str, Any],
    max_origins: int | None = None,
) -> float | None:
    """Run train.py with given config and return the score.

    Returns:
        Score (avg_mase) or None on failure.
    """
    from evaluate import evaluate
    from prepare import load_panel
    from train import apply_config_overrides, run

    config_path = write_config(config)

    try:
        # Apply config overrides in this process
        apply_config_overrides(str(config_path))

        panel = load_panel()
        fr = run(panel, era="validation", max_origins=max_origins)
        eval_result = evaluate(fr, panel)

        # Extract score from summary
        if not eval_result.summary:
            logger.warning("No summary metrics — evaluation produced no results")
            return None

        # Average across all horizons
        scores = [
            eval_result.summary[h].get(SCORE_METRIC, float("inf"))
            for h in eval_result.summary
        ]
        return float(sum(scores) / len(scores)) if scores else None

    except Exception as e:
        logger.exception("Run failed: %s", e)
        return None


def propose_random_config(
    available_covariates: list[str],
) -> tuple[dict[str, Any], str]:
    """Propose a random configuration from the search space.

    Used as a baseline comparison for the LLM-guided search.
    """
    rng = np.random.default_rng()

    # Random covariate subset (0-5 covariates)
    n_covs = rng.integers(0, min(6, len(available_covariates) + 1))
    covs = list(rng.choice(available_covariates, size=n_covs, replace=False)) if n_covs > 0 else []

    # Random transforms on covariates
    transform_options = ["none", "log_diff", "pct_change_1", "pct_change_12", "standardize_60", "ma_3"]
    transforms = {}
    for c in covs:
        t = rng.choice(transform_options)
        if t != "none":
            transforms[c] = t

    # Random context length
    context_options = [None, 24, 36, 48, 64, 96, 128]
    context_length = rng.choice(context_options)

    # Random fine-tuning (low probability to keep fast)
    fine_tune = bool(rng.random() < 0.2)
    fine_tune_steps = int(rng.choice([100, 500, 1000]))
    fine_tune_lr = float(10 ** rng.uniform(-6, -4))

    config = {
        "covariates": covs,
        "transforms": transforms,
        "context_length": int(context_length) if context_length is not None else None,
        "fine_tune": fine_tune,
        "fine_tune_steps": fine_tune_steps,
        "fine_tune_lr": fine_tune_lr,
    }
    description = _summarize_config(config)
    return config, description


def reset_train_config() -> None:
    """Reset train.py config to defaults by removing override file."""
    if CURRENT_CONFIG_PATH.exists():
        CURRENT_CONFIG_PATH.unlink()


# ---------------------------------------------------------------------------
# Main search loop
# ---------------------------------------------------------------------------


def search_loop(
    max_iterations: int | None = None,
    resume: bool = False,
    mode: str = "llm",
    program_path: str | None = None,
) -> None:
    """Run the search loop.

    Args:
        max_iterations: Stop after this many iterations (None = run forever).
        resume: If True, resume from saved state.
        mode: "llm" for LLM-guided search, "random" for random search baseline.
        program_path: Path to alternative program.md for LLM prompt.
    """
    from prepare import load_panel

    panel = load_panel()
    available_covariates = panel.covariates()

    # Initialize or resume state
    state: SearchState
    if resume:
        loaded = SearchState.load()
        if loaded:
            state = loaded
            logger.info("Resumed from iteration %d (best score: %.4f)",
                        state.iteration, state.best_score)
        else:
            logger.warning("No saved state found, starting fresh")
            state = SearchState(start_time=datetime.now().isoformat())
    else:
        state = SearchState(start_time=datetime.now().isoformat())

    # Establish baseline if starting fresh
    if state.iteration == 0:
        logger.info("Establishing baseline (zero-shot, no covariates)...")
        baseline_config = DEFAULT_CONFIG.copy()

        # Quick baseline (for filtering)
        logger.info("  Quick baseline (%d origins)...", QUICK_EVAL_ORIGINS)
        quick_baseline = run_and_evaluate(baseline_config, max_origins=QUICK_EVAL_ORIGINS)
        if quick_baseline is None:
            logger.error("Baseline quick evaluation failed. Cannot proceed.")
            return
        logger.info("  Quick baseline score: %.4f", quick_baseline)

        # Full baseline (for accept/reject decisions)
        logger.info("  Full baseline (all origins)...")
        full_baseline = run_and_evaluate(baseline_config, max_origins=None)
        if full_baseline is None:
            logger.error("Baseline full evaluation failed. Cannot proceed.")
            return
        logger.info("  Full baseline score: %.4f", full_baseline)

        state.baseline_score = full_baseline
        state.best_score = full_baseline
        state.best_config = baseline_config

        record = IterationRecord(
            iteration=0,
            config=baseline_config,
            quick_score=quick_baseline,
            full_score=full_baseline,
            status="accepted",
            description="baseline (zero-shot, univariate)",
            runtime_seconds=0,
            timestamp=datetime.now().isoformat(),
        )
        state.history.append(record)
        _log_iteration(record)
        state.save()

        logger.info("Baseline: quick=%.4f, full=%.4f", quick_baseline, full_baseline)

    # Main loop
    iteration = state.iteration
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        state.iteration = iteration
        iter_start = time.time()

        logger.info("\n{'=' * 60}")
        logger.info("ITERATION %d (best: %.4f)", iteration, state.best_score)
        logger.info("{'=' * 60}")

        # 1. Propose config
        try:
            if mode == "random":
                overrides, description = propose_random_config(available_covariates)
            else:
                overrides, description = propose_config(
                    state, available_covariates, program_override=program_path
                )
        except Exception as e:
            logger.exception("Config proposal failed: %s", e)
            record = IterationRecord(
                iteration=iteration, config={}, quick_score=None, full_score=None,
                status="error", description=f"proposal failed: {e}",
                runtime_seconds=time.time() - iter_start,
                timestamp=datetime.now().isoformat(),
            )
            state.history.append(record)
            _log_iteration(record)
            state.save()
            continue

        # 2. Merge with best config
        candidate_config = merge_config(state.best_config, overrides)
        logger.info("Proposed config: %s", json.dumps(overrides, default=str))

        # 3. Quick evaluation (subsampled origins)
        logger.info("Quick evaluation (%d origins)...", QUICK_EVAL_ORIGINS)
        quick_score = run_and_evaluate(candidate_config, max_origins=QUICK_EVAL_ORIGINS)

        if quick_score is None:
            record = IterationRecord(
                iteration=iteration, config=candidate_config,
                quick_score=None, full_score=None,
                status="error", description=f"{description} (run failed)",
                runtime_seconds=time.time() - iter_start,
                timestamp=datetime.now().isoformat(),
            )
            state.history.append(record)
            _log_iteration(record)
            state.save()
            logger.warning("Quick evaluation failed, skipping.")
            continue

        logger.info("Quick score: %.4f (best: %.4f)", quick_score, state.best_score)

        # 4. If quick eval shows improvement, run full evaluation
        full_score = None
        if quick_score < state.best_score:
            logger.info("Quick eval improved! Running full evaluation (120 origins)...")
            full_score = run_and_evaluate(candidate_config, max_origins=None)

            if full_score is not None:
                logger.info("Full score: %.4f (best: %.4f)", full_score, state.best_score)

        # 5. Accept or reject
        accepted = False
        if full_score is not None and full_score < state.best_score:
            state.best_score = full_score
            state.best_config = candidate_config
            accepted = True
            logger.info("ACCEPTED — new best: %.4f", full_score)
        else:
            logger.info("REJECTED — keeping best: %.4f", state.best_score)

        # 6. Log
        record = IterationRecord(
            iteration=iteration,
            config=candidate_config,
            quick_score=quick_score,
            full_score=full_score,
            status="accepted" if accepted else "rejected",
            description=description,
            runtime_seconds=time.time() - iter_start,
            timestamp=datetime.now().isoformat(),
        )
        state.history.append(record)
        _log_iteration(record)
        state.save()

    # Cleanup
    reset_train_config()
    logger.info("\nSearch complete after %d iterations.", iteration)
    logger.info("Best score: %.4f", state.best_score)
    logger.info("Best config: %s", json.dumps(state.best_config, indent=2, default=str))


def _log_iteration(record: IterationRecord) -> None:
    """Append iteration to JSONL log file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEARCH_LOG_PATH, "a") as f:
        f.write(json.dumps(asdict(record), default=str) + "\n")


def show_status() -> None:
    """Print current search state."""
    state = SearchState.load()
    if state is None:
        print("No search state found. Run search.py to start.")
        return

    print("Search State")
    print(f"  Started: {state.start_time}")
    print(f"  Iterations: {state.iteration}")
    print(f"  Baseline score: {state.baseline_score:.4f}")
    print(f"  Best score: {state.best_score:.4f}")
    print(f"  Improvement: {(1 - state.best_score / state.baseline_score) * 100:.1f}%")
    print("\nBest config:")
    print(f"  {json.dumps(state.best_config, indent=4, default=str)}")

    if state.history:
        print("\nRecent iterations:")
        for rec in state.history[-10:]:
            score = f"{rec.full_score:.4f}" if rec.full_score else f"~{rec.quick_score:.4f}" if rec.quick_score else "N/A"
            print(f"  [{rec.iteration}] {rec.status:10s}  score={score}  {rec.description}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-guided search over forecasting pipeline configuration",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="Stop after N iterations (default: run until interrupted)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from saved search state",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current search status and exit",
    )
    parser.add_argument(
        "--mode", type=str, default="llm", choices=["llm", "random"],
        help="Search mode: 'llm' (Claude-guided) or 'random' (random sampling baseline)",
    )
    parser.add_argument(
        "--program", type=str, default=None,
        help="Path to alternative program.md for the LLM prompt (e.g., configs/program_blind.md)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.status:
        show_status()
        return

    search_loop(
        max_iterations=args.max_iterations,
        resume=args.resume,
        mode=args.mode,
        program_path=args.program,
    )


if __name__ == "__main__":
    main()
