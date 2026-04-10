# STATUS.md — Autoresearch Macro

**Stage:** REVISION-PLAN-4 — three-country expansion for IJF submission
**Target journal:** International Journal of Forecasting
**Collaborators:** Leif Anders Thorsrud
**Last updated:** 2026-04-10

## Revision-plan-4 progress

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Audit Norway results against paper | Complete |
| 1 | Unified evaluation pipeline (`build_forecast_errors.py`, `tables/generate_tables.py`) | Complete |
| 2 | Three-country data layer (Norway, Canada, Sweden) | Complete |
| 3 | Baseline suite (classical + BVAR + Elastic Net + manual economist benchmark) | Complete |
| 4 | Search experiments | In progress (see matrix below) |
| 5 | Mechanism + robustness (ablations, subperiods, re-fit) | Partial — leave-one-out still missing |
| 6 | Manuscript rebuild | Not started |
| 7 | IJF reproducibility package | Not started |

## Search experiment matrix

| Country | Informed LLM | Blind LLM | Random | Greedy | Manual benchmark |
|---------|--------------|-----------|--------|--------|------------------|
| Norway  | seeds 42, 123, 456 (50 iter) | seed 42 (50 iter) | seed 42 (50 iter) | 200 iter | Locked in config |
| Canada  | seed 42 (50 iter) | — | seed 42 (50 iter) | 3 iter | Locked in config |
| Sweden  | seed 42 (50 iter) | — | seed 42 (50 iter) | 5 iter | Locked in config |

**Outstanding search runs:**
- Blind LLM search for Canada and Sweden (seed 42, 50 iter each)
- Additional seeds (123, 456) for Canada/Sweden informed and random search, if compute permits
- Greedy stepwise search needs more iterations for Canada (currently 3) and Sweden (5)

## Norway results snapshot

**Validation era (2006-2015, avg MASE across targets and horizons):**

| Method | MASE | vs baseline |
|--------|------|-------------|
| Zero-shot baseline | 0.9991 | — |
| Informed LLM (seed 42) | 0.9745 | -2.5% |
| Informed LLM (seed 123) | 0.9529 | -4.6% |
| Informed LLM (seed 456) | 0.9572 | -4.2% |
| Blind LLM (seed 42) | 0.9798 | -1.9% |
| Random search (seed 42) | 0.9423 | -5.7% |
| Greedy stepwise | 0.9222 | -7.7% |

**Best informed config (seed 42):** `sp500 + policy_rate + fed_funds + nok_usd`, LoRA fine-tune 500 steps, lr 1e-5
**Best blind config (seed 42):** `sp500 + vix`, LoRA fine-tune 100 steps, lr 1e-5

The blind agent finds equity/risk proxies (`sp500`, `vix`) without hints but does not rediscover monetary/exchange-rate covariates. The informed agent's picks are economically interpretable.

## Canada results snapshot (validation MASE)

| Method | MASE |
|--------|------|
| Informed LLM (seed 42) | 0.8425 |
| Random search (seed 42) | 0.8474 |
| Greedy stepwise | 0.8406 |

## Sweden results snapshot (validation MASE)

| Method | MASE |
|--------|------|
| Informed LLM (seed 42) | 1.0056 |
| Random search (seed 42) | 0.9363 |
| Greedy stepwise | 0.9919 |

Sweden is the one country where random search currently beats the informed LLM — an interesting heterogeneity result to explore.

## Model: amazon/chronos-2 (120M)

- AutoGluon 1.5.0 via `"Chronos-2"` hyperparameter key
- Native covariate support (past + known future)
- LoRA fine-tuning (r=8, α=16)
- 8,192 context length

## Recent engineering fixes

- **2026-04-08:** `time_limit` raised from 300s → 1800s in `fit_predictor()`. AutoGluon 1.5.0 model loading takes 260-340s, so the old limit killed fine-tune runs before training started.
- **2026-04-08:** Added `--tag` flag to `search.py` so blind and informed runs with the same seed get separate state files.

## Current to-dos

- [ ] Run blind LLM search for Canada and Sweden
- [ ] Consolidate three-country `forecast_errors.parquet`
- [ ] Leave-one-component-out ablation for each country's best config
- [ ] Regenerate manuscript tables for three-country evaluation
- [ ] Draft Phase 6 manuscript rewrite

## Known data limitations

- Norway: Industrial production (SSB 14208) ends 2023M12; unemployment (13760) only from 2006M01; house prices (seasonally adjusted) only from 2005Q1
- Canada: Target choice for industrial output is Monthly GDP at basic prices (Table 36-10-0434-01). See `metadata/canada_target_decision.md`.
- Sweden: Follows SCB PxWeb API; partner-area activity variable is euro-area GDP (same as Norway)
