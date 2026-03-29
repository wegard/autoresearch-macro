# CONTEXT.md — Session Resume

**Last updated:** 2026-03-29

## Current state

First search experiment complete: 30 iterations, 4 accepted improvements, **6.6% improvement** over zero-shot baseline. The agent discovered that Chronos-2 (120M) forecasts Norwegian macro variables best with oil prices, the policy rate, and US inflation as covariates, using a 96-month context window.

## What happened

- 2026-03-27: Project initiated. Research design drafted. Autoresearch cloned.
- 2026-03-28: Full implementation session — data pipeline, baselines, train.py, search.py, evaluate.py, webapp. Fixed SSB table IDs, Norges Bank keys. 90 tests passing.
- 2026-03-29:
  - Switched from chronos-bolt-small (20M) to amazon/chronos-2 (120M)
  - Fixed fine-tuning bugs (wrong param name, module identity, default arg binding, baseline scoring)
  - Ran first search experiment: 30 iterations
  - Agent found best config: `covariates=[brent_crude, policy_rate, us_cpi], context_length=96`
  - MASE improved from 1.9443 (baseline) to 1.8158 (best), a 6.6% improvement

## Search trajectory

| Iter | Config change | MASE | Status |
|------|--------------|------|--------|
| 0 | Baseline | 1.9443 | accepted |
| 9 | context_length=96 | 1.8635 | accepted (-4.2%) |
| 15 | + brent_crude | 1.8472 | accepted (-5.0%) |
| 18 | + policy_rate | 1.8326 | accepted (-5.7%) |
| 27 | + us_cpi | 1.8158 | accepted (-6.6%) |

26 iterations rejected. Fine-tuning, transforms, exchange rates, and additional covariates all hurt.

## Next steps

1. Run best config on **test era** (2016+) for final out-of-sample results
2. Consider more search iterations (fine-tuning with very few steps was close: 1.8160 vs 1.8158)
3. Phase 4: ablation analysis — decompose the 6.6% gain into covariate vs context effects
4. Update webapp with search trajectory visualization
5. Discuss with Leif

## Critical files

| File | Role |
|------|------|
| `src/train.py` | Agent sandbox — amazon/chronos-2 via "Chronos-2" key |
| `src/search.py` | LLM-guided outer loop controller |
| `results/search_state.json` | Persisted search state (30 iterations) |
| `results/search_log.jsonl` | Full iteration log (94 entries across all runs) |
