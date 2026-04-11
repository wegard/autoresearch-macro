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

## Sweden results snapshot (validation MASE, **3 targets**)

| Method | MASE | Notes |
|--------|------|-------|
| Zero-shot baseline | 1.0056 | — |
| Informed LLM s42 (current state) | 1.0056 | No improvement found |
| Informed LLM s42 (lost on 2026-04-08) | 0.9663 | `house_prices, ctx=36` — verified reproducible 2026-04-11 |
| Blind LLM s42 | 1.0056 | No improvement found in 50 iterations |
| Random search s42 | 0.9363 | `policy_rate, global_epu, brent_crude, fx_usd` + transforms, ctx=48 |
| Greedy stepwise | 0.9919 | — |

**Sweden caveats (added 2026-04-11):**
1. **Only 3 targets** — `retail_sales` is dropped because the SCB table publishes from 2023-01 only (no validation-era coverage). MASE numbers above are not directly comparable to Norway/Canada (4 targets each). See `metadata/sweden_target_notes.md`.
2. **The informed LLM result of 1.0056 is misleading** — the original 2026-04-02 informed run found 0.9663 at iteration 21 (`house_prices, ctx=36`), which was lost when the run was relaunched on 2026-04-08 without `--resume` and the state file got reset. The lost result was reproduced exactly by re-running the config on 2026-04-11. Search.py now has an overwrite guard (commit 57de78b) to prevent this from recurring.
3. **Quick→full eval gating is biased high for Sweden** — baseline quick MASE is 1.0274 while full is 1.0056 (2.1% gap), so candidate configs need to score below 1.0056 on quick eval before full eval is even triggered. In the current informed and blind runs, **0 of 50** proposals cleared this threshold. The two-phase eval pre-filter is dropping legitimate candidates for Sweden.

## Model: amazon/chronos-2 (120M)

- AutoGluon 1.5.0 via `"Chronos-2"` hyperparameter key
- Native covariate support (past + known future)
- LoRA fine-tuning (r=8, α=16)
- 8,192 context length

## Recent engineering fixes

- **2026-04-08:** `time_limit` raised from 300s → 1800s in `fit_predictor()`. AutoGluon 1.5.0 model loading takes 260-340s, so the old limit killed fine-tune runs before training started.
- **2026-04-08:** Added `--tag` flag to `search.py` so blind and informed runs with the same seed get separate state files.
- **2026-04-11:** Added overwrite guard to `search.py` (commit 57de78b). The loop now refuses to start a fresh run when a state file with prior progress exists, unless `--overwrite` is passed. This is the foot-gun that destroyed the lost Sweden 0.9663 result.
- **2026-04-11:** Dropped `retail_sales` from the Sweden panel via `DROPPED_VARIABLES` in `prepare_sweden.py`. Sweden now has 3 targets instead of 4. See `metadata/sweden_target_notes.md`.

## Current to-dos

- [ ] Run blind LLM search for Canada and Sweden
- [ ] Consolidate three-country `forecast_errors.parquet`
- [ ] Leave-one-component-out ablation for each country's best config
- [ ] Regenerate manuscript tables for three-country evaluation
- [ ] Draft Phase 6 manuscript rewrite

## Known data limitations

- Norway: Industrial production (SSB 14208) ends 2023M12; unemployment (13760) only from 2006M01; house prices (seasonally adjusted) only from 2005Q1
- Canada: Target choice for industrial output is Monthly GDP at basic prices (Table 36-10-0434-01). See `metadata/canada_target_decision.md`.
- **Sweden: `retail_sales` is dropped (3 targets, not 4).** The SCB table `HA/HA0101/HA0101B/Detoms07N` only publishes from 2023-01, with no validation-era coverage. Discovered 2026-04-11 while investigating Sweden's stuck blind LLM search. Sweden MASE numbers are computed across only 3 targets (cpi, industrial_production, unemployment) and are not directly comparable to the 4-target Norway and Canada averages. See `metadata/sweden_target_notes.md`.
