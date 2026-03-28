# CONTEXT.md — Session Resume

**Last updated:** 2026-03-28

## Current state

All infrastructure is built. Phase 0 and Phase 1 are complete. The project is ready to run the first agentic search experiment (Phase 3).

## What happened

- 2026-03-27: Project initiated. Research design drafted. Autoresearch cloned.
- 2026-03-28: Full implementation session:
  - Verified and fixed SSB table IDs against live API (6 tables changed: unemployment → 13760, exports/imports → 08803, policy rate key fixed, S&P 500 → NASDAQCOM, euro GDP quarterly fix)
  - Built `evaluate.py` (evaluation harness with results storage and comparison)
  - Built `baselines.py` (5 methods: random walk, seasonal naive, AR, ARIMA, ETS)
  - Built `train.py` (Chronos-2 via AutoGluon, config override mechanism)
  - Built `search.py` (LLM-guided outer loop with Claude API)
  - Wrote `program.md` (full agent instructions with domain knowledge)
  - Wrote `configs/search_space.yml` (parameter ranges)
  - Ran all baselines + zero-shot Chronos-2 on validation era
  - 90 tests, all passing

## Key results so far

- ARIMA is the strongest classical baseline (avg RMSE 2.64 at h=12)
- Zero-shot Chronos-2 (bolt-small, univariate) does not beat ARIMA (avg RMSE 2.92)
- This confirms hypothesis H2: economy-specific adaptation is needed

## Next steps

1. **Run first search experiment** — see EXPERIMENT-1.md
2. Test Chronos-2 with manual covariate selections (oil, FX, etc.)
3. Fine-tuning experiments (Phase 2)
4. Analyze search trajectory and discovered configurations

## Critical files

| File | Lines | Role |
|------|-------|------|
| `src/prepare.py` | 1237 | Data pipeline (LOCKED) |
| `src/train.py` | 478 | Agent sandbox (EDITABLE) |
| `src/evaluate.py` | 451 | Evaluation harness (LOCKED) |
| `src/search.py` | 557 | Outer loop controller |
| `src/baselines.py` | 547 | Classical baselines |
| `program.md` | 82 | Agent instructions |
| `configs/search_space.yml` | 43 | Search parameter ranges |
