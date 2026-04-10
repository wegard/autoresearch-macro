# Decision Log

## 2026-03-27 — Project setup

**Decision:** Create project workspace, build own search loop rather than forking autoresearch.

**Reasoning:** Karpathy's autoresearch is designed for single-GPU vision/language tasks with a single train.py. We need a forecasting-specific loop with rolling validation, structured search space, and Chronos-2/AutoGluon backend. Clone for reference, build our own.

**Decision:** Start with Chronos-2 specifically, but design the search loop model-agnostic from day one.

**Reasoning:** Chronos-2 has native covariate support and probabilistic output — good starting point. But the stronger paper tests whether agentic search generalizes across foundation models.

**Decision:** Monthly macro panel as initial target set.

**Reasoning:** More data points than quarterly, cleaner evaluation, natural starting point. Quarterly GDP / mixed-frequency are extensions.

## 2026-03-28 — Implementation sprint

**Decision:** Replace 3 SSB table IDs after live API verification.

**Reasoning:** Original table IDs were guesses from the spec. Verification revealed: 01598 (unemployment) returns 400, 13967 was election data not unemployment, 08799 (trade) had 13k commodity codes. Replaced with: 13760 (LFS unemployment), 08803 (trade main figures). Also fixed Norges Bank policy rate SDMX key.

**Decision:** Switch from FRED SP500 to NASDAQCOM for stock market proxy.

**Reasoning:** FRED restricts SP500 to ~10 years of data. NASDAQCOM goes back to 1971, sufficient for pre-2006 training window.

**Decision:** Use AutoGluon TimeSeriesPredictor (not raw ChronosPipeline) as the model interface.

**Reasoning:** ChronosPipeline had version compatibility issues (`input_patch_size` config error). AutoGluon wraps Chronos cleanly with fit-once-predict-many pattern.

**Decision:** Default model size: chronos-bolt-small (~20M params).

**Reasoning:** Fits in 2GB VRAM, fast inference (~1.3s per origin). Good for search iterations where speed matters. Can upgrade to bolt-base for final evaluation.

**Decision:** LLM-guided search (not structured random search) as the primary search strategy.

**Reasoning:** The paper's contribution is specifically about agentic search. Structured search can serve as a comparison baseline but is not the core experiment.

**Decision:** Two-phase evaluation during search: quick (20 origins) → full (120 origins).

**Reasoning:** Full evaluation takes ~3 minutes. Quick evaluation takes ~30 seconds. Only run full eval when quick eval shows improvement. Dramatically increases iteration speed.

**Decision:** Use MASE as the primary search metric (not RMSE).

**Reasoning:** MASE is scale-independent (each variable's error is normalized by the naive forecast error). This prevents the search from over-optimizing for the variable with the largest scale.

## 2026-03-28 — First search experiment (10 iterations)

**Finding:** Zero-shot Chronos-2 Bolt is effectively a deterministic univariate model. Covariates, grouping, num_samples, and the fine_tune flag all produced identical scores (1.2414 MASE) in the 10-iteration smoke test.

**Root cause:** Several config dimensions have no effect in the current architecture:

- **Covariates** are added as extra columns in the TimeSeriesDataFrame, but Chronos Bolt ignores them in zero-shot mode. It only reads the `target` column.
- **fine_tune=True** is passed to `fit()`, but the fit-once-predict-many architecture means fine-tuning only runs on the first origin's data. The fine-tuned model may not generalize to later origins, and AutoGluon may be short-circuiting if it detects the model is already loaded.
- **num_samples** has no effect because Chronos Bolt uses a single deterministic forward pass (not ancestral sampling like the original Chronos).
- **grouping** (univariate vs all_targets) doesn't change predictions because each item is forecasted independently by Chronos Bolt regardless.

**What did have an effect:** Context length (96 vs unlimited) changed the quick-eval score from 1.2414 to 1.2089, but this didn't hold on full evaluation (1.9094), suggesting the subsample was misleading.

**Decision needed:** To make the search meaningful, the architecture needs one or more of:

1. **Proper covariate integration** — use a model that natively supports covariates (e.g., original Chronos with sampling, or a different foundation model like TimesFM), or implement channel-stacking where covariates are fed as separate items.
2. **Per-origin fine-tuning** — fine-tune a fresh model for each forecast origin (expensive: ~120 fit calls per evaluation). Could subsample origins for the search phase.
3. **Hybrid approach** — use Chronos for the base forecast and add a regression step on top that uses covariates (covariate_regressor in AutoGluon).
4. **Switch to original Chronos** (non-Bolt) which supports probabilistic sampling and may respond differently to context changes.

**Status:** Resolved by switching to amazon/chronos-2 (120M). See 2026-03-29 entry.

## 2026-03-29 — Switch to amazon/chronos-2 (120M)

**Decision:** Replace chronos-bolt-small (20M) with amazon/chronos-2 (120M) as the foundation model.

**Reasoning:** Chronos-Bolt is fundamentally univariate — it ignores covariates in zero-shot mode and fine-tuning has no effect. Chronos-2 (120M) is architecturally different:
- `_supports_known_covariates = True` and `_supports_past_covariates = True` (native multivariate)
- LoRA fine-tuning built in (default r=8, lora_alpha=16)
- Cross-learning across time series in a batch
- 8192 context length
- Only one size: 120M parameters

**Implementation:**
- Changed `MODEL_PATH` to `"amazon/chronos-2"`
- Changed hyperparameter key from `"Chronos"` to `"Chronos-2"` (selects `Chronos2Model` in AutoGluon)
- Updated fine-tune defaults: lr=1e-5 (was 1e-4), steps=1000 (was 100)
- Updated search_space.yml: steps=[100,500,1000,2000], lr=[1e-6,1e-4]

**Results:** Zero-shot Chronos-2 (120M) is competitive with ARIMA at h=1 (avg RMSE 1.171 vs 1.164) and beats ARIMA on industrial production (2.483 vs 2.532). Falls behind at h=12 (2.820 vs 2.641). This is the gap the search loop aims to close using covariates and fine-tuning.

**Also fixed in this session:**
- Wrong hyperparameter name (`learning_rate` → `fine_tune_lr`) — fine-tuning was silently ignored
- Module identity bug in `apply_config_overrides` — `import train` creates a separate module from `__main__`
- Default argument binding — `fit_predictor()` defaults bound at definition time, not call time
- Baseline scoring bug — baseline was scored on 20 subsampled origins but compared against full 120-origin scores

## 2026-03-29 — First successful search experiment (30 iterations)

**Result:** 6.6% MASE improvement (1.9443 → 1.8158) over zero-shot baseline across 30 iterations.

**Search trajectory (4 accepted improvements):**
1. context_length=96 (MASE 1.8635, -4.2%)
2. + brent_crude (1.8472, -5.0%)
3. + policy_rate (1.8326, -5.7%)
4. + us_cpi (1.8158, -6.6%)

**Best config:** `covariates=[brent_crude, policy_rate, us_cpi], context_length=96, fine_tune=false`

**Key findings:**
- Oil prices, monetary policy rate, and US inflation are the optimal covariates for Norwegian macro
- 96-month (8-year) context window outperforms both shorter and longer windows
- Adding exchange rates (NOK/EUR, NOK/USD), credit, or exports hurts performance
- Transforms on covariates (log_diff, pct_change, standardize) don't help
- LoRA fine-tuning consistently degrades performance (overfits on first origin's data)
- Iteration 30 was tantalizingly close: fine_tune with 100 steps at 5e-6 lr scored 1.8160 vs best 1.8158
- The discovered covariate set is economically interpretable — exactly what a macro economist would expect for a small open oil-exporting economy

## 2026-03-29 — Continued search (iterations 31-50)

**Result:** Two additional accepted improvements. MASE improved from 1.8158 to 1.8129 (6.8% total improvement over baseline).

**New accepted configs:**
- Iter 39: Added nok_eur as 4th covariate (1.8158 → 1.8129). Earlier attempts with NOK/EUR had failed because they weren't combined with the right covariate set and context length.
- Iter 45: LoRA fine-tuning accepted (100 steps, lr=5e-6). Very conservative settings were key — all previous fine-tuning attempts with 500+ steps or lr>1e-5 had hurt performance.

**Search convergence:** By iteration ~45, the agent was mostly proposing configs that matched or slightly worsened the best. Iterations 46-50 showed no improvement, suggesting the search has approximately converged within the current search space.

**Final best config:**
```json
{
  "covariates": ["brent_crude", "policy_rate", "us_cpi", "nok_eur"],
  "context_length": 96,
  "fine_tune": true,
  "fine_tune_steps": 100,
  "fine_tune_lr": 5e-06
}
```

## 2026-04-08 — AutoGluon 1.5.0 fine-tune time_limit bug

**Finding:** After `uv sync --extra ml` pulled AutoGluon 1.5.0, every fine-tune run in the blind Norway search silently produced zero forecasts with "Trainer has no fit models that can predict."

**Root cause:** In 1.5.0, Chronos-2 model loading on this machine takes ~260-340s (HuggingFace cache check + weight load). `train.py` was passing `time_limit=300` for fine-tune and `time_limit=30` for zero-shot, so AutoGluon killed the model before training even started and returned an empty predictor.

**Fix:** Raised `time_limit` to 1800s for both modes. Actual training budget is controlled by `fine_tune_steps`; `time_limit` is just a safety guardrail.

**Side effect:** Setting `HF_HUB_OFFLINE=1` further cuts startup time because AutoGluon skips the HuggingFace HEAD check.

## 2026-04-08 — --tag flag for blind vs informed runs

**Decision:** Added a `--tag` argument to `src/search.py` so blind and informed LLM runs with the same seed write to separate state/log files.

**Reasoning:** The state file was keyed only by `mode + seed`, so `--program prompts/blind.md --seed 42` was resuming the existing informed run rather than starting a fresh blind search. Adding `--tag blind` gives `search_state_llm_blind_42.json`.

## 2026-04-09 — Blind Norway search (50 iterations)

**Setup:** `prompts/blind.md` strips all domain knowledge about the Norwegian economy — the agent only sees generic variable names and must discover useful covariates without hints.

**Result:** Blind search found a 1.9% improvement (baseline 0.9991 → best 0.9798 MASE) and converged on `sp500 + vix` with LoRA fine-tuning (100 steps, lr=1e-5). Informed search at seed 42 reached 0.9745 with the economically interpretable `sp500 + policy_rate + fed_funds + nok_usd`.

**Interpretation:** The domain-blind agent discovered risk/equity indicators on its own, but did not rediscover the monetary and exchange-rate covariates that the informed agent found. This is evidence that domain knowledge helps the agent narrow in on macro-relevant variables — not just any covariate set yields the same validation gains.

## 2026-03-29 — Test era evaluation

**Result:** The agent-tuned config does not generalize to the test era (2016+).

**Test era RMSE (avg across targets):**

| Method | h=1 | h=3 | h=6 | h=12 |
|--------|-----|-----|-----|------|
| Random walk | 1.413 | 1.759 | 2.115 | 2.609 |
| ARIMA | 1.450 | 1.797 | 2.284 | 2.815 |
| Chronos-2 zero-shot | 1.463 | 1.772 | 2.212 | 2.790 |
| Chronos-2 agent-tuned | 1.461 | 1.847 | 2.346 | 3.230 |

**Key findings:**
- Random walk is the strongest method on the test era — regime changes (COVID, inflation) favor the naive baseline
- Zero-shot Chronos-2 beats ARIMA at h=3/6/12, suggesting the foundation model is more robust to structural breaks
- The agent-tuned config overfits: covariates and fine-tuning that helped in 2006-2015 hurt in 2016+
- Exception: unemployment improves with agent-tuned config at all horizons (0.435 vs 0.475 RW at h=1)
- The overfitting result is itself publishable — it demonstrates a fundamental limitation of validation-era pipeline search for macro forecasting in the presence of structural breaks
