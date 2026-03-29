# Revision Plan — Round 1

Based on four AI referee reports (Gemini-DR, Gemini-DT, GPT-DR, GPT-Pro). All recommend **major revision**. This plan prioritizes substantial experimental and methodological changes over cosmetic fixes.

**Last updated:** 2026-03-29

---

## Consensus issues (all 4 referees agree)

### R1. Add multivariate baselines — CRITICAL

**Problem:** The agent uses 4 covariates, but all classical baselines are univariate. This makes the comparison fundamentally unfair.

**Action:** Implement two multivariate baselines using the same 14-variable covariate pool:
1. **BVAR** — Bayesian VAR with Minnesota priors (standard in macro forecasting)
2. **Factor model** — Extract principal components from the covariate panel, use as regressors in direct h-step forecasting equations

These must use the same pseudo-real-time discipline and rolling evaluation as everything else.

**Implementation:** Add `BVARBaseline` and `FactorModelBaseline` classes to `src/baselines.py`. Use `statsmodels` for VAR and `scikit-learn` for PCA. Run on both validation and test eras.

**Priority:** Must-do. Without this, the paper's comparison is invalid.

---

### R2. Statistical significance testing — CRITICAL

**Problem:** All results are reported as point estimates with no inference. The IJF expects Diebold-Mariano tests.

**Action:**
1. Implement pairwise Diebold-Mariano tests with HAC standard errors (Newey-West) for multi-step forecast errors
2. Report p-values for key comparisons: ARIMA vs Chronos-2 zero-shot, zero-shot vs agent-tuned, BVAR vs Chronos-2
3. Consider Model Confidence Set (MCS) procedure for selecting the best method

**Implementation:** Add a `diebold_mariano()` function to `src/evaluate.py`. Apply to all pairwise method comparisons on both eras. Report in results tables with significance stars.

**Priority:** Must-do.

---

### R3. Fix fine-tuning protocol — CRITICAL

**Problem:** Fine-tuning once on 2006 data and freezing for 10+ years artificially handicaps the agent-tuned model. Classical baselines re-estimate at every origin.

**Action:** Implement and compare three fine-tuning protocols:
1. **Static** (current): fit once on first origin, freeze
2. **Periodic**: re-tune every 12 origins (annually) using expanding window
3. **Per-origin**: re-tune at each origin (expensive but fair)

At minimum, implement periodic re-tuning and compare against the static approach. This isolates whether the test-era failure is due to stale weights vs broken covariate relationships.

**Implementation:** Modify `src/train.py` `run()` function to support a `retune_interval` parameter. Re-run the best config with periodic fine-tuning on both eras.

**Priority:** Must-do. This is the single most impactful experiment — if periodic fine-tuning fixes the overfitting, the paper's story changes fundamentally.

---

### R4. Complete the manuscript

**Problem:** Multiple TODO placeholders, missing appendices, "preliminary and incomplete" label.

**Action:** Remove all TODOs, fill Appendix C with per-variable tables, remove "preliminary" label, add Leif's email, write acknowledgments.

**Priority:** Must-do but straightforward.

---

## Strong consensus (3/4 referees)

### R5. Ablation of pipeline components

**Problem:** We report the final search result but don't isolate which component drives the test-era failure.

**Action:** Run the following ablation on the test era:
1. Zero-shot baseline (no changes)
2. + context_length=96 only
3. + context_length=96 + brent_crude
4. + context_length=96 + brent_crude + policy_rate
5. + context_length=96 + brent_crude + policy_rate + us_cpi
6. + context_length=96 + brent_crude + policy_rate + us_cpi + nok_eur
7. Full best config (all above + LoRA fine-tuning)

This traces the search trajectory on the test era and shows exactly where things go wrong.

**Implementation:** Write `scripts/ablation_analysis.py` that runs each config and collects test-era metrics. Produce an ablation table for the paper.

**Priority:** High. This is the analysis that makes the overfitting story convincing.

---

### R6. Compare LLM search to random search

**Problem:** No evidence that the LLM agent adds value over standard AutoML approaches.

**Action:** Implement a structured random search baseline:
- Same search space as the LLM agent
- Same evaluation protocol (quick + full)
- Same 50-iteration budget
- Random sampling from the search space (no LLM reasoning)

Compare: does LLM-guided search find better configurations faster?

**Implementation:** Add a `--mode random` flag to `src/search.py` that samples configs uniformly from the search space instead of calling Claude.

**Priority:** High. If random search finds equivalent configs, the "agentic" claim is weakened (but the overfitting finding still stands).

---

### R7. Per-variable results tables

**Problem:** Aggregate RMSE/MASE hides heterogeneity. The agent-tuned config helps unemployment but hurts retail sales — this is invisible in the current tables.

**Action:** Add comprehensive per-variable × per-horizon tables for:
- Validation era (all 6+ methods)
- Test era (4 key methods)
- Test era by subperiod

These go in Appendix C and are referenced from the main text.

**Implementation:** Extend `scripts/subperiod_analysis.py` to produce full per-variable tables. Generate LaTeX table code.

**Priority:** High.

---

### R8. Metric consistency

**Problem:** The search optimizes MASE but results tables report RMSE. This is confusing and inconsistent.

**Action:**
- Report MASE as the primary metric throughout (since it's the search objective and is scale-independent)
- Include RMSE as a secondary metric in appendix tables
- Ensure the aggregation method is clearly described (per-variable MASE, then averaged across variables)

**Priority:** Medium-high. Easy to fix.

---

## Important but lower priority

### R9. Address prompt contamination concern

**Problem:** Gemini-DR notes that `program.md` tells the agent to prioritize oil and exchange rates — so the "discovery" is partially guided.

**Action:** Run the search with a **domain-blind prompt** — remove all Norwegian-specific hints from program.md and see if the agent still discovers the same covariates. This directly tests whether the LLM's reasoning adds value beyond the prompt.

**Implementation:** Create `configs/program_blind.md` with generic instructions. Run 50 iterations. Compare discovered configs.

**Priority:** Medium. Strengthens the "agentic discovery" claim if the agent finds the same covariates without hints.

---

### R10. Probabilistic evaluation

**Problem:** Chronos-2 outputs distributions but we only evaluate point forecasts.

**Action:** Extract quantile forecasts from Chronos-2 and evaluate using:
- Continuous Ranked Probability Score (CRPS)
- Pinball loss at key quantiles (10%, 25%, 50%, 75%, 90%)
- Prediction interval coverage

**Implementation:** Modify `src/train.py` to save quantile forecasts alongside point forecasts. Add CRPS computation to `src/evaluate.py`.

**Priority:** Medium. Adds depth but doesn't change the core findings.

---

### R11. Rolling/expanding validation window

**Problem:** The fixed 2006-2015 validation window means the search can't adapt to post-2015 patterns.

**Action:** Test an alternative protocol where the validation window rolls forward:
- Retune every 3 years using the most recent 10 years as validation
- Compare against the fixed-window approach

**Implementation:** Modify `src/search.py` to support rolling validation windows. Run a shorter search (20 iterations) with 3-year rolling windows.

**Priority:** Medium. Addresses the overfitting concern directly but is computationally expensive.

---

### R12. Narrative reframe

**Problem:** GPT-Pro notes the paper oscillates between "agent improves forecasts" and "agent fails." Should lead with the cautionary finding.

**Action:** Restructure the introduction to:
1. Lead with the question: can automated search improve foundation model macro forecasts?
2. Preview the positive validation result
3. Immediately flag the overfitting failure
4. Frame the paper's contribution as documenting both promise and limitations

Revise the title to be more specific and cautionary. Current title is too broad ("small open economies" from one country).

**Suggested title:** "Agentic Pipeline Search for Foundation Model Macro Forecasting: Promise and Overfitting in Norwegian Data"

**Priority:** Medium. Important for positioning but doesn't require experiments.

---

## Explicitly out of scope for this revision

- **True real-time data vintages** — would require SSB vintage database access; noted as limitation
- **Additional countries** — single-country study is acceptable for IJF if framed correctly
- **Additional foundation models** — would dilute the focus; mention in future work
- **Per-origin fine-tuning** — computationally prohibitive (120× the current cost)

---

## Implementation priority order

| # | Task | Type | Effort | Impact |
|---|------|------|--------|--------|
| 1 | BVAR + Factor model baselines (R1) | New code + experiments | Large | Critical |
| 2 | Diebold-Mariano tests (R2) | New code | Medium | Critical |
| 3 | Periodic fine-tuning (R3) | Code change + experiments | Large | Critical |
| 4 | Ablation analysis (R5) | Experiments | Medium | High |
| 5 | Random search comparison (R6) | Code change + experiments | Medium | High |
| 6 | Per-variable tables (R7) | Analysis + LaTeX | Small | High |
| 7 | Metric consistency (R8) | Paper editing | Small | Medium |
| 8 | Complete manuscript (R4) | Paper editing | Small | Must-do |
| 9 | Prompt contamination test (R9) | Experiments | Medium | Medium |
| 10 | Probabilistic evaluation (R10) | Code + experiments | Medium | Medium |
| 11 | Narrative reframe (R12) | Paper editing | Small | Medium |
| 12 | Rolling validation (R11) | Code + experiments | Large | Medium |

---

## Files to create/modify

| File | Change |
|------|--------|
| `src/baselines.py` | Add BVAR and Factor model classes |
| `src/evaluate.py` | Add `diebold_mariano()` function |
| `src/train.py` | Add `retune_interval` parameter to `run()` |
| `src/search.py` | Add `--mode random` for random search baseline |
| `scripts/ablation_analysis.py` | New — run step-by-step ablation on test era |
| `tests/test_baselines.py` | Add tests for BVAR and Factor model |
| `paper/main.tex` | Major revision — new tables, reframed narrative |
| `METHODOLOGY.md` | Update with new baselines, DM tests, fine-tuning protocols |
