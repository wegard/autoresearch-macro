# CONTEXT.md — Session Resume

**Last updated:** 2026-03-29

## Current state

Search experiment complete: 50 iterations, 6 accepted improvements, **6.8% MASE improvement** over zero-shot baseline. Best config: covariates=[brent_crude, policy_rate, us_cpi, nok_eur], context_length=96, LoRA fine-tune (100 steps, 5e-6 lr).

## What happened

- 2026-03-27: Project initiated. Research design drafted. Autoresearch cloned.
- 2026-03-28: Full implementation session — data pipeline, baselines, train.py, search.py, evaluate.py, webapp. Fixed SSB table IDs, Norges Bank keys. 90 tests passing.
- 2026-03-29:
  - Switched from chronos-bolt-small (20M) to amazon/chronos-2 (120M)
  - Fixed fine-tuning bugs (wrong param name, module identity, default arg binding, baseline scoring)
  - Ran first search experiment: 30 iterations
  - Agent found best config: `covariates=[brent_crude, policy_rate, us_cpi], context_length=96`
  - MASE improved from 1.9443 (baseline) to 1.8158 (best), a 6.6% improvement

## Search trajectory (50 iterations, 6 accepted)

| Iter | Config change | MASE | Status |
|------|--------------|------|--------|
| 0 | Baseline | 1.9443 | accepted |
| 9 | context_length=96 | 1.8635 | accepted (-4.2%) |
| 15 | + brent_crude | 1.8472 | accepted (-5.0%) |
| 18 | + policy_rate | 1.8326 | accepted (-5.7%) |
| 27 | + us_cpi | 1.8158 | accepted (-6.6%) |
| 39 | + nok_eur | 1.8129 | accepted (-6.8%) |
| 45 | + LoRA fine-tune (100 steps, 5e-6) | 1.8129 | accepted (-6.8%) |

44 iterations rejected. Search converged by ~iter 45.

## Next steps

1. Phase 4: ablation analysis — decompose gains, analyze validation-to-test overfitting
2. Regenerate forecast visualizations with test-era data
3. Consider per-variable search (agent-tuned config helps unemployment but hurts others)
4. Discuss with Leif: test-era overfitting, paper implications

## Test era results (2016+)

The agent-tuned config does NOT generalize to the test era. At h=12, it's the worst method (RMSE 3.23 vs random walk 2.61). The search overfit to validation-era patterns.

However, zero-shot Chronos-2 beats ARIMA at h=3/6/12 on the test era — the foundation model handles regime changes (COVID, inflation) better than classical methods. Unemployment is the exception where the agent-tuned config is best at all horizons.

## Critical files

| File | Role |
|------|------|
| `src/train.py` | Agent sandbox — amazon/chronos-2 via "Chronos-2" key |
| `src/search.py` | LLM-guided outer loop controller |
| `results/search_state.json` | Persisted search state (30 iterations) |
| `results/search_log.jsonl` | Full iteration log (94 entries across all runs) |
