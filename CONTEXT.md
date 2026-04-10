# CONTEXT.md — Session Resume

**Last updated:** 2026-04-10

## Current state

Executing `paper/REVISION-PLAN-4.md` — a three-country expansion (Norway + Canada + Sweden) targeting the International Journal of Forecasting. Phases 0-3 are complete. Phase 4 (search experiments) is in progress.

## Phase 4 search matrix

| Country | Informed LLM | Blind LLM | Random | Greedy |
|---------|--------------|-----------|--------|--------|
| Norway  | seeds 42/123/456 | seed 42 (50 iter) | seed 42 | 200 iter |
| Canada  | seed 42 | pending | seed 42 | 3 iter |
| Sweden  | seed 42 | pending | seed 42 | 5 iter |

**Immediate next steps:**
1. Blind LLM search for Canada and Sweden (seed 42, 50 iter each)
2. More greedy iterations for Canada and Sweden
3. Leave-one-component-out ablation for each country's best config (Phase 5)
4. Consolidate three-country `forecast_errors.parquet` and regenerate tables

## Best configs so far (validation MASE)

| Country | Method | MASE | Config |
|---------|--------|------|--------|
| Norway | Informed LLM s42 | 0.9745 | `sp500, policy_rate, fed_funds, nok_usd`, ft 500 steps, lr 1e-5 |
| Norway | Informed LLM s123 | 0.9529 | — |
| Norway | Informed LLM s456 | 0.9572 | — |
| Norway | Blind LLM s42 | 0.9798 | `sp500, vix`, ft 100 steps, lr 1e-5 |
| Norway | Random s42 | 0.9423 | — |
| Norway | Greedy | 0.9222 | — |
| Canada | Informed LLM s42 | 0.8425 | — |
| Sweden | Informed LLM s42 | 1.0056 | — |

Blind Norway found risk/equity indicators (`sp500 + vix`) without domain hints but missed the monetary and FX covariates that the informed agent picked up.

## Recent engineering fixes (2026-04-08/09)

1. **`time_limit` bug in train.py.** AutoGluon 1.5.0 Chronos-2 model loading takes 260-340s on this machine; the prior `time_limit=300` for fine-tune (and `30` for zero-shot) killed the predictor before training started. Raised to 1800s.
2. **`--tag` flag in search.py.** State files were keyed only by `mode+seed`, so blind/informed runs with the same seed overwrote each other. `--tag blind` now creates `search_state_llm_blind_42.json`.
3. **Run with `HF_HUB_OFFLINE=1`** to skip HuggingFace HEAD checks — cuts ~30s per model load.
4. **Install both extras together:** `uv sync --extra ml --extra dev`. Syncing only one extra uninstalls the other.

## Critical files

| File | Role |
|------|------|
| `paper/REVISION-PLAN-4.md` | Current execution spec (three-country IJF revision) |
| `STATUS.md` | Phase-by-phase progress + per-country results |
| `src/search.py` | Search controller — `--country`, `--mode`, `--program`, `--tag`, `--seed` |
| `src/train.py` | Agent sandbox — Chronos-2 via AutoGluon `"Chronos-2"` key |
| `src/prepare.py` / `prepare_canada.py` / `prepare_sweden.py` | Country-specific data pipelines (locked) |
| `configs/manual_economist_benchmarks.yaml` | Locked manual benchmarks per country |
| `prompts/{blind,informed_*}.md` | LLM search prompts |
| `metadata/variable_catalog.csv` | Authoritative metadata for all three countries |
| `results/{norway,canada,sweden}/search_state_*.json` | Per-run search state |
