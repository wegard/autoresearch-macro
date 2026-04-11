"""Outer loop controller for the autoresearch-macro search.

Orchestrates an LLM-guided search over the forecasting pipeline configuration.
Uses Claude API to propose config changes, evaluates them via train.py,
and accepts/rejects based on validation performance.

Supports multiple search modes (LLM, random, greedy) and multiple countries.

Usage:
    python src/search.py                                    # Norway LLM search
    python src/search.py --country canada --mode llm --program prompts/informed_canada.md
    python src/search.py --country sweden --mode random --seed 42 --max-iterations 50
    python src/search.py --country norway --mode greedy --max-iterations 200
    python src/search.py --resume                           # Resume from saved state
    python src/search.py --status                           # Show current search state
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

import shutil

import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

RESULTS_DIR = PROJECT_ROOT / "results"
CONFIG_DIR = PROJECT_ROOT / "configs"
CURRENT_CONFIG_PATH = CONFIG_DIR / "current_config.json"
PROGRAM_PATH = PROJECT_ROOT / "program.md"
SEARCH_SPACE_PATH = CONFIG_DIR / "search_space.yml"

COUNTRIES = ["norway", "canada", "sweden"]

# Legacy paths (for backward compat with existing Norway results)
SEARCH_LOG_PATH = RESULTS_DIR / "search_log.jsonl"
SEARCH_STATE_PATH = RESULTS_DIR / "search_state.json"


def _search_paths(
    country: str, mode: str, seed: int, tag: str | None = None,
) -> tuple[Path, Path]:
    """Get parameterized search state and log file paths."""
    if country == "norway" and mode == "llm" and seed == 0 and tag is None:
        # Backward compat with existing Norway results
        return SEARCH_STATE_PATH, SEARCH_LOG_PATH
    base = RESULTS_DIR / country
    base.mkdir(parents=True, exist_ok=True)
    suffix = f"{mode}_{tag}_{seed}" if tag else f"{mode}_{seed}"
    state_path = base / f"search_state_{suffix}.json"
    log_path = base / f"search_log_{suffix}.jsonl"
    return state_path, log_path

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
    """Persistent state for the search loop.

    ``best_quick_score`` tracks the *quick-eval* score of the current best
    config. The search uses this (not best_score, which is the full-eval
    score) as the gating threshold to decide whether to promote a candidate
    to full evaluation. This is direction-agnostic to the quick-vs-full
    baseline gap and was introduced after Sweden's broken gating was found
    on 2026-04-11.
    """

    iteration: int = 0
    best_score: float = float("inf")
    best_quick_score: float = float("inf")
    best_config: dict[str, Any] = field(default_factory=dict)
    baseline_score: float = float("inf")
    history: list[IterationRecord] = field(default_factory=list)
    start_time: str = ""

    def to_json(self) -> str:
        data = {
            "iteration": self.iteration,
            "best_score": self.best_score,
            "best_quick_score": self.best_quick_score,
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
            # Backwards compat: old state files don't have best_quick_score.
            # Default to inf and try to recover from history below.
            best_quick_score=data.get("best_quick_score", float("inf")),
            best_config=data["best_config"],
            baseline_score=data["baseline_score"],
            start_time=data.get("start_time", ""),
        )
        for h in data.get("history", []):
            state.history.append(IterationRecord(**h))

        # Backwards compat recovery: if best_quick_score is missing, infer it
        # from the history by finding the accepted record whose full_score
        # matches best_score (i.e., the iteration that produced the best).
        # Without this, resumed old runs would treat every gate check as
        # permissive (inf) and waste compute on full evals that always reject.
        if state.best_quick_score == float("inf") and state.history:
            for rec in reversed(state.history):
                if (rec.status == "accepted"
                        and rec.full_score is not None
                        and rec.quick_score is not None
                        and abs(rec.full_score - state.best_score) < 1e-9):
                    state.best_quick_score = rec.quick_score
                    break

        return state

    def save(self, path: Path | None = None) -> None:
        save_path = path or SEARCH_STATE_PATH
        _robust_write(save_path, self.to_json())

    @classmethod
    def load(cls, path: Path | None = None) -> SearchState | None:
        load_path = path or SEARCH_STATE_PATH
        if load_path.exists():
            return cls.from_json(load_path.read_text())
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


def _robust_write(path: Path, text: str, retries: int = 5, delay: float = 2.0) -> None:
    """Write text to a file with retries for transient filesystem errors (e.g. SSHFS)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            path.write_text(text)
            return
        except OSError as e:
            if attempt < retries - 1:
                logger.warning("Write to %s failed (attempt %d/%d): %s — retrying in %.0fs",
                               path.name, attempt + 1, retries, e, delay)
                time.sleep(delay)
                delay *= 2
            else:
                raise


def write_config(config: dict[str, Any]) -> Path:
    """Write config to JSON file for train.py to read."""
    _robust_write(CURRENT_CONFIG_PATH, json.dumps(config, indent=2))
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
            if rec.full_score is not None:
                score_str = f"{rec.full_score:.4f}"
            elif rec.quick_score is not None:
                score_str = f"~{rec.quick_score:.4f}"
            else:
                score_str = "N/A"
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


def _eval_in_child(config_json: str, max_origins: int | None,
                    country: str, result_pipe: Any) -> None:
    """Target function for subprocess evaluation.

    Runs in a forked child process so all file descriptors (PyTorch, joblib,
    safetensors) are reclaimed by the OS when the child exits.
    """
    config_path = None
    try:
        import sys
        import tempfile
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from evaluate import evaluate
        from train import apply_config_overrides, run

        config = json.loads(config_json)
        # Write to a unique temp file to avoid race conditions when
        # multiple search processes run in parallel.
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".json", dir=CONFIG_DIR, prefix="cfg_")
        config_path = Path(tmp)
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
        apply_config_overrides(str(config_path))

        if country == "norway":
            from prepare import load_panel
            panel = load_panel()
        elif country == "canada":
            from prepare_canada import load_panel_canada
            panel = load_panel_canada()
        elif country == "sweden":
            from prepare_sweden import load_panel_sweden
            panel = load_panel_sweden()
        else:
            from prepare import load_panel
            panel = load_panel()

        fr = run(panel, era="validation", max_origins=max_origins)
        eval_result = evaluate(fr, panel)

        if not eval_result.summary:
            result_pipe.send(None)
            return

        scores = [
            eval_result.summary[h].get(SCORE_METRIC, float("inf"))
            for h in eval_result.summary
        ]
        result_pipe.send(float(sum(scores) / len(scores)) if scores else None)
    except Exception as e:
        logger.exception("Child eval failed: %s", e)
        result_pipe.send(None)
    finally:
        if config_path is not None:
            config_path.unlink(missing_ok=True)


# Country name used by the current search_loop invocation (set in search_loop)
_current_country: str = "norway"


def run_and_evaluate(
    config: dict[str, Any],
    max_origins: int | None = None,
    panel: Any | None = None,
) -> float | None:
    """Run train.py with given config and return the score.

    Evaluation runs in a child process so that all file descriptors from
    PyTorch, AutoGluon, joblib, etc. are reclaimed by the OS when the
    child exits. This prevents the 'Too many open files' crashes during
    long greedy search runs.

    Args:
        config: Pipeline configuration to evaluate.
        max_origins: Subsample origins for quick eval (None = all).
        panel: Ignored (kept for API compat). The child loads its own panel.

    Returns:
        Score (avg_mase) or None on failure.
    """
    import multiprocessing as mp

    parent_conn, child_conn = mp.Pipe(duplex=False)
    child = mp.Process(
        target=_eval_in_child,
        args=(json.dumps(config), max_origins, _current_country, child_conn),
    )
    child.start()
    child_conn.close()  # Parent doesn't write to the pipe

    # Wait for result — model loading alone can take 5+ min, fine-tuning adds more
    timeout = 3600  # 1 hour
    if parent_conn.poll(timeout):
        score = parent_conn.recv()
    else:
        logger.error("Child evaluation timed out after %ds", timeout)
        child.kill()
        score = None

    child.join(timeout=30)
    if child.exitcode and child.exitcode != 0:
        logger.warning("Child process exited with code %d", child.exitcode)
        score = None

    parent_conn.close()
    return score


def propose_random_config(
    available_covariates: list[str],
    rng: np.random.Generator | None = None,
) -> tuple[dict[str, Any], str]:
    """Propose a random configuration from the search space.

    Used as a baseline comparison for the LLM-guided search.
    """
    if rng is None:
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
# Greedy stepwise search
# ---------------------------------------------------------------------------

# Full action space for greedy search
CONTEXT_LENGTH_OPTIONS = [None, 24, 36, 48, 64, 96, 128]
FINE_TUNE_STEPS_OPTIONS = [100, 500, 1000, 2000]
FINE_TUNE_LR_OPTIONS = [1e-6, 5e-6, 1e-5, 5e-5, 1e-4]


def _generate_greedy_neighbors(
    current: dict[str, Any],
    available_covariates: list[str],
) -> list[tuple[dict[str, Any], str]]:
    """Generate all single-step neighbor configs from the current best.

    Returns list of (config_overrides, description) tuples.
    """
    neighbors: list[tuple[dict[str, Any], str]] = []
    current_covs = set(current.get("covariates", []))

    # 1. Add each available covariate (one at a time)
    for cov in available_covariates:
        if cov not in current_covs:
            new_covs = sorted(current_covs | {cov})
            neighbors.append((
                {"covariates": new_covs},
                f"add {cov}",
            ))

    # 2. Remove each selected covariate (one at a time)
    for cov in current_covs:
        new_covs = sorted(current_covs - {cov})
        neighbors.append((
            {"covariates": new_covs},
            f"remove {cov}",
        ))

    # 3. Change context_length
    current_ctx = current.get("context_length")
    for ctx in CONTEXT_LENGTH_OPTIONS:
        if ctx != current_ctx:
            neighbors.append((
                {"context_length": ctx},
                f"context={ctx}",
            ))

    # 4. Toggle fine_tune
    current_ft = current.get("fine_tune", False)
    if current_ft:
        neighbors.append((
            {"fine_tune": False},
            "disable fine-tune",
        ))
    else:
        neighbors.append((
            {"fine_tune": True, "fine_tune_steps": 500, "fine_tune_lr": 5e-6},
            "enable fine-tune (500 steps, 5e-6)",
        ))

    # 5. Fine-tune hyperparameters (only if fine-tune is on)
    if current.get("fine_tune"):
        current_steps = current.get("fine_tune_steps", 1000)
        for steps in FINE_TUNE_STEPS_OPTIONS:
            if steps != current_steps:
                neighbors.append((
                    {"fine_tune_steps": steps},
                    f"ft_steps={steps}",
                ))

        current_lr = current.get("fine_tune_lr", 1e-5)
        for lr in FINE_TUNE_LR_OPTIONS:
            if abs(lr - current_lr) / current_lr > 0.1:
                neighbors.append((
                    {"fine_tune_lr": lr},
                    f"ft_lr={lr:.0e}",
                ))

    return neighbors


def propose_greedy_config(
    state: SearchState,
    available_covariates: list[str],
    panel: Any | None = None,
    rejected_descriptions: set[str] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Greedy stepwise: quick-eval all neighbors, return the best one.

    Returns (None, description) if no improving neighbor is found (convergence).
    Skips neighbors whose descriptions are in rejected_descriptions (i.e.,
    neighbors that passed quick eval but failed full eval on a previous round).
    """
    neighbors = _generate_greedy_neighbors(state.best_config, available_covariates)
    rejected = rejected_descriptions or set()

    # Filter out previously rejected neighbors
    candidates = [(o, d) for o, d in neighbors if d not in rejected]
    skipped = len(neighbors) - len(candidates)
    if skipped:
        logger.info("Greedy step: evaluating %d neighbors (%d skipped as previously rejected)...",
                     len(candidates), skipped)
    else:
        logger.info("Greedy step: evaluating %d neighbors...", len(candidates))

    best_neighbor = None
    # Compare neighbor quick scores against the best config's quick score,
    # not its full score. Same reason as the LLM/random gating fix on
    # 2026-04-11 — when quick eval is biased relative to full eval, gating
    # against the full score systematically misses improvements.
    best_quick_score = state.best_quick_score
    best_description = ""

    for overrides, description in candidates:
        candidate = merge_config(state.best_config, overrides)
        score = run_and_evaluate(
            candidate, max_origins=QUICK_EVAL_ORIGINS, panel=panel)
        if score is not None and score < best_quick_score:
            best_quick_score = score
            best_neighbor = overrides
            best_description = description
            logger.info("  Neighbor %s: %.4f (improvement!)", description, score)

    if best_neighbor is None:
        return None, "no improving neighbor"

    logger.info("Best neighbor: %s (quick=%.4f)", best_description, best_quick_score)
    return best_neighbor, f"greedy: {best_description}"


# ---------------------------------------------------------------------------
# Main search loop
# ---------------------------------------------------------------------------


def search_loop(
    max_iterations: int | None = None,
    resume: bool = False,
    mode: str = "llm",
    program_path: str | None = None,
    country: str = "norway",
    seed: int = 0,
    tag: str | None = None,
    overwrite: bool = False,
) -> None:
    """Run the search loop.

    Args:
        max_iterations: Stop after this many iterations (None = run forever).
        resume: If True, resume from saved state.
        mode: "llm", "random", or "greedy".
        program_path: Path to alternative program.md for LLM prompt.
        country: Country to run search for.
        seed: Random seed for reproducibility.
        tag: Optional tag for distinguishing runs (e.g., "blind").
        overwrite: If True, allow starting fresh even if a state file with prior
            results exists (otherwise refuse). Ignored when ``resume`` is True.
    """
    global _current_country
    _current_country = country

    # Parameterized output paths
    state_path, log_path = _search_paths(country, mode, seed, tag=tag)

    logger.info("Search: country=%s, mode=%s, seed=%d", country, mode, seed)
    logger.info("  State: %s", state_path)
    logger.info("  Log: %s", log_path)

    # Refuse to overwrite an existing state file unless --resume or --overwrite.
    # This prevents accidentally destroying prior search results, and runs the
    # check BEFORE any heavy imports / model loading so the user gets immediate
    # feedback. (Sweden lost a 0.9663 informed result this way on 2026-04-08.)
    if not resume:
        existing = SearchState.load(state_path)
        if existing is not None and existing.iteration > 0 and not overwrite:
            logger.error(
                "State file already exists at %s with %d iterations and best "
                "score %.4f. Refusing to overwrite. Use --resume to continue, "
                "or --overwrite to start fresh and discard prior results.",
                state_path, existing.iteration, existing.best_score,
            )
            return

    # Pre-import autogluon in the parent process so forked children inherit
    # the loaded modules. This prevents failures when another uv process
    # modifies the shared virtualenv during a parallel run.
    try:
        import autogluon.timeseries  # noqa: F401
        logger.info("Pre-imported autogluon.timeseries in parent process")
    except ImportError:
        logger.warning("autogluon.timeseries not available — child evals may fail")

    from baselines import load_country_panel

    panel = load_country_panel(country)
    available_covariates = panel.covariates()

    # Seeded RNG for random/greedy modes
    rng = np.random.default_rng(seed) if seed != 0 else np.random.default_rng()

    # Initialize or resume state
    state: SearchState
    if resume:
        loaded = SearchState.load(state_path)
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
        quick_baseline = run_and_evaluate(
            baseline_config, max_origins=QUICK_EVAL_ORIGINS, panel=panel)
        if quick_baseline is None:
            logger.error("Baseline quick evaluation failed. Cannot proceed.")
            return
        logger.info("  Quick baseline score: %.4f", quick_baseline)

        # Full baseline (for accept/reject decisions)
        logger.info("  Full baseline (all origins)...")
        full_baseline = run_and_evaluate(baseline_config, max_origins=None, panel=panel)
        if full_baseline is None:
            logger.error("Baseline full evaluation failed. Cannot proceed.")
            return
        logger.info("  Full baseline score: %.4f", full_baseline)

        state.baseline_score = full_baseline
        state.best_score = full_baseline
        state.best_quick_score = quick_baseline
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
        _log_iteration(record, log_path)
        state.save(state_path)

        logger.info("Baseline: quick=%.4f, full=%.4f", quick_baseline, full_baseline)

    # Main loop
    iteration = state.iteration
    consecutive_errors = 0
    # Track greedy neighbors that passed quick-eval but failed full-eval,
    # so we don't waste iterations retrying the same deceptive neighbor.
    greedy_rejected: set[str] = set()
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        state.iteration = iteration
        iter_start = time.time()

        logger.info("\n{'=' * 60}")
        logger.info("ITERATION %d (best: %.4f)", iteration, state.best_score)
        logger.info("{'=' * 60}")

        # 1. Propose config (with backoff on consecutive connection errors)
        try:
            if mode == "random":
                overrides, description = propose_random_config(
                    available_covariates, rng=rng)
            elif mode == "greedy":
                overrides, description = propose_greedy_config(
                    state, available_covariates, panel=panel,
                    rejected_descriptions=greedy_rejected)
                if overrides is None:
                    logger.info("Greedy search converged — no improving neighbors.")
                    break
            else:
                overrides, description = propose_config(
                    state, available_covariates, program_override=program_path
                )
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors >= 3:
                wait = min(300, 30 * (consecutive_errors - 2))
                logger.warning(
                    "Connection error (%d consecutive). Waiting %ds before retry...",
                    consecutive_errors, wait)
                time.sleep(wait)
            logger.error("Config proposal failed: %s", e)
            record = IterationRecord(
                iteration=iteration, config={}, quick_score=None, full_score=None,
                status="error", description=f"proposal failed: {e}",
                runtime_seconds=time.time() - iter_start,
                timestamp=datetime.now().isoformat(),
            )
            state.history.append(record)
            _log_iteration(record, log_path)
            state.save(state_path)
            continue

        # 2. Merge with best config
        candidate_config = merge_config(state.best_config, overrides)
        logger.info("Proposed config: %s", json.dumps(overrides, default=str))

        # 3. Quick evaluation (subsampled origins)
        logger.info("Quick evaluation (%d origins)...", QUICK_EVAL_ORIGINS)
        quick_score = run_and_evaluate(
            candidate_config, max_origins=QUICK_EVAL_ORIGINS, panel=panel)

        if quick_score is None:
            record = IterationRecord(
                iteration=iteration, config=candidate_config,
                quick_score=None, full_score=None,
                status="error", description=f"{description} (run failed)",
                runtime_seconds=time.time() - iter_start,
                timestamp=datetime.now().isoformat(),
            )
            state.history.append(record)
            _log_iteration(record, log_path)
            state.save(state_path)
            logger.warning("Quick evaluation failed, skipping.")
            continue

        logger.info("Quick score: %.4f (best quick: %.4f, best full: %.4f)",
                    quick_score, state.best_quick_score, state.best_score)

        # 4. If quick eval shows improvement, run full evaluation.
        # Gate is on best_quick_score (not best_score / full) so the test is
        # symmetric regardless of whether quick eval is biased high or low
        # vs full eval — see Sweden investigation 2026-04-11 in log.md.
        full_score = None
        if quick_score < state.best_quick_score:
            logger.info("Quick eval improved! Running full evaluation...")
            full_score = run_and_evaluate(
                candidate_config, max_origins=None, panel=panel)

            if full_score is not None:
                logger.info("Full score: %.4f (best: %.4f)", full_score, state.best_score)

        # 5. Accept or reject. Acceptance is on the FULL score (this is the
        # real metric); only the gating threshold uses the quick score.
        accepted = False
        if full_score is not None and full_score < state.best_score:
            state.best_score = full_score
            state.best_quick_score = quick_score
            state.best_config = candidate_config
            accepted = True
            # New best config — all neighbors are fresh again
            greedy_rejected.clear()
            logger.info("ACCEPTED — new best: %.4f", full_score)
        else:
            # Track rejected greedy neighbors so we don't retry them.
            # Strip the "greedy: " prefix to match the description format
            # used by _generate_greedy_neighbors.
            if mode == "greedy" and full_score is not None:
                raw_desc = description.removeprefix("greedy: ")
                greedy_rejected.add(raw_desc)
                logger.info("REJECTED — keeping best: %.4f (marking '%s' as tried)",
                            state.best_score, raw_desc)
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
        _log_iteration(record, log_path)
        state.save(state_path)

    # Cleanup
    reset_train_config()
    logger.info("\nSearch complete after %d iterations.", iteration)
    logger.info("Best score: %.4f", state.best_score)
    logger.info("Best config: %s", json.dumps(state.best_config, indent=2, default=str))


def _log_iteration(record: IterationRecord, log_path: Path | None = None) -> None:
    """Append iteration to JSONL log file."""
    path = log_path or SEARCH_LOG_PATH
    line = json.dumps(asdict(record), default=str) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            with open(path, "a") as f:
                f.write(line)
            return
        except OSError as e:
            if attempt < 4:
                delay = 2.0 * (2 ** attempt)
                logger.warning("Log append to %s failed (attempt %d/5): %s — retrying in %.0fs",
                               path.name, attempt + 1, e, delay)
                time.sleep(delay)
            else:
                raise


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
        description="Search over forecasting pipeline configuration",
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
        "--mode", type=str, default="llm", choices=["llm", "random", "greedy"],
        help="Search mode: 'llm', 'random', or 'greedy' (stepwise)",
    )
    parser.add_argument(
        "--program", type=str, default=None,
        help="Path to prompt file for the LLM (e.g., prompts/informed_canada.md)",
    )
    parser.add_argument(
        "--country", type=str, default="norway", choices=COUNTRIES,
        help="Country to run search for (default: norway)",
    )
    parser.add_argument(
        "--seed", type=int, default=0,
        help="Random seed for reproducibility (default: 0 = unseeded)",
    )
    parser.add_argument(
        "--tag", type=str, default=None,
        help="Optional tag for state/log filenames (e.g., 'blind')",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Allow starting fresh even if a state file with prior results exists "
             "(otherwise the run is refused). Ignored when --resume is set.",
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
        country=args.country,
        seed=args.seed,
        tag=args.tag,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
