# STATUS.md — Autoresearch Macro

**Stage:** Phase 3 complete (50 iterations), Phase 4 analysis next
**Target:** TBD
**Collaborators:** Leif Anders Thorsrud
**Last updated:** 2026-03-29

## Submission history

Not yet written.

## Search experiment results (50 iterations, avg MASE)

| Iter | Config change | MASE | vs Baseline |
|------|--------------|------|-------------|
| 0 | Baseline (univariate, all context) | 1.9443 | — |
| 9 | + context_length=96 | 1.8635 | -4.2% |
| 15 | + brent_crude | 1.8472 | -5.0% |
| 18 | + policy_rate | 1.8326 | -5.7% |
| 27 | + us_cpi | 1.8158 | -6.6% |
| 39 | + nok_eur | 1.8129 | -6.8% |
| **45** | **+ LoRA fine-tune (100 steps, 5e-6)** | **1.8129** | **-6.8%** |

**Best config:**
```json
{
  "covariates": ["brent_crude", "policy_rate", "us_cpi", "nok_eur"],
  "context_length": 96,
  "fine_tune": true,
  "fine_tune_steps": 100,
  "fine_tune_lr": 5e-06
}
```

**Key findings:**
- 4 covariates optimal: oil, monetary policy, global inflation, exchange rate
- 96-month (8-year) context window is optimal
- LoRA fine-tuning works with very conservative settings (100 steps, lr=5e-6)
- Aggressive fine-tuning (500+ steps, lr>1e-5) consistently hurts
- Transforms on covariates don't help — raw levels work best
- The search converged by iteration ~45 — diminishing returns after

## Validation era results (2006-2015, average RMSE across targets)

| Method | h=1 | h=3 | h=6 | h=12 |
|--------|-----|-----|-----|------|
| Random walk | 1.202 | 1.533 | 1.958 | 2.683 |
| Seasonal naive | 2.645 | 2.639 | 2.645 | 3.670 |
| AR(p) | 1.164 | 1.543 | 1.968 | 2.949 |
| **ARIMA** | **1.164** | **1.504** | **1.910** | **2.641** |
| ETS | 1.186 | 1.561 | 2.022 | 2.890 |
| Chronos-2 (120M) zero-shot | 1.171 | 1.542 | 1.989 | 2.820 |

## Current to-dos

- [ ] Run best config on test era (2016+) for final results
- [ ] Phase 4 ablation analysis (decompose gains by covariate, context, fine-tuning)
- [ ] Regenerate forecast visualizations with best config
- [ ] Discuss with Leif: results, next steps, paper outline

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
