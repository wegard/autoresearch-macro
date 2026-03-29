# STATUS.md — Autoresearch Macro

**Stage:** Phase 3 complete (first search experiment), Phase 4 analysis next
**Target:** TBD
**Collaborators:** Leif Anders Thorsrud
**Last updated:** 2026-03-29

## Submission history

Not yet written.

## What's built

### Data pipeline (Phase 0) — done
- `src/prepare.py` (1237 lines) — SSB, FRED, Norges Bank downloads with pseudo-real-time discipline
- 18 variables, 951 months (1947-01 to 2026-03)
- 36 tests in `tests/test_prepare.py`

### Evaluation harness — done
- `src/evaluate.py` (451 lines) — ForecastResult, EvaluationResult, save/load, comparison tables
- 11 tests in `tests/test_evaluate.py`

### Baselines (Phase 1) — done
- `src/baselines.py` (547 lines) — 5 methods: random walk, seasonal naive, AR(p), ARIMA, ETS
- All evaluated on validation era (2006-2015, 120 monthly origins)

### Chronos-2 scaffold — done
- `src/train.py` — amazon/chronos-2 (120M params), AutoGluon "Chronos-2" key
- Native covariate support, LoRA fine-tuning
- 12 tests in `tests/test_train.py`

### Search loop (Phase 3) — first experiment complete
- `src/search.py` — LLM-guided outer loop with Claude API
- **30 iterations completed, 4 accepted improvements, 6.6% improvement over baseline**
- Best config: brent_crude + policy_rate + us_cpi, context_length=96
- 16 tests in `tests/test_search.py`

### Web dashboard — done
- `webapp/` — Quarto + Observable Plot interactive site (6 pages)

### Totals
- **~5,000 lines** of Python (source + tests)
- **90 tests**, all passing

## Validation era results (2006-2015, average RMSE across targets)

| Method | h=1 | h=3 | h=6 | h=12 |
|--------|-----|-----|-----|------|
| Random walk | 1.202 | 1.533 | 1.958 | 2.683 |
| Seasonal naive | 2.645 | 2.639 | 2.645 | 3.670 |
| AR(p) | 1.164 | 1.543 | 1.968 | 2.949 |
| **ARIMA** | **1.164** | **1.504** | **1.910** | **2.641** |
| ETS | 1.186 | 1.561 | 2.022 | 2.890 |
| Chronos-2 (120M) zero-shot | 1.171 | 1.542 | 1.989 | 2.820 |

## Search experiment results (30 iterations, avg MASE)

| Iter | Config | MASE | vs Baseline |
|------|--------|------|-------------|
| 0 | Baseline (univariate, all context) | 1.9443 | — |
| 9 | + context_length=96 | 1.8635 | -4.2% |
| 15 | + brent_crude | 1.8472 | -5.0% |
| 18 | + policy_rate | 1.8326 | -5.7% |
| **27** | **+ us_cpi** | **1.8158** | **-6.6%** |

**Best config found by the agent:**
```json
{
  "covariates": ["brent_crude", "policy_rate", "us_cpi"],
  "context_length": 96,
  "fine_tune": false
}
```

**Key findings:**
- Oil prices, monetary policy, and US inflation are the most informative covariates
- 96-month (8-year) context window is optimal
- Adding more covariates (exchange rates, credit, exports) hurts performance
- Transforms on covariates don't help — raw levels work best
- LoRA fine-tuning consistently degrades performance (overfits on small training data)
- The discovered covariate set is economically interpretable

## Current to-dos

- [ ] Run best config on test era (2016+) for final results
- [ ] Run more search iterations (fine-tuning exploration)
- [ ] Phase 4 ablation analysis (decompose gains)
- [ ] Update webapp with search trajectory data
- [ ] Discuss with Leif: results, next steps

## Model: amazon/chronos-2 (120M)

- **Native covariate support** — both past and known future covariates
- **LoRA fine-tuning** — default r=8, lora_alpha=16
- **Cross-learning** — joint predictions across time series
- Accessed via AutoGluon `"Chronos-2"` model key

## Known data limitations

- Industrial production (table 14208) ends 2023M12
- Unemployment (table 13760) only from 2006M01
- House prices (seasonally adjusted) only from 2005Q1
- NOK/EUR only from 1999 (euro introduction)
