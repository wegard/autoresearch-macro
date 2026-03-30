# Revision Plan — Round 2

Based on three AI referee reports (Gemini-DR, GPT-DR, GPT-Pro). All recommend **major revision**. The round-1 ablation, random search, and subperiod analysis were well-received, but critical gaps remain in metrics, baselines, statistical testing, and several new experiments.

**Last updated:** 2026-03-30

---

## Items carried over from Round 1 (not yet addressed)

### R2.1. MASE definition is wrong — CRITICAL

**Problem (all 3 referees):** Section 4.3 defines MASE as "MAE / MAE_naive" but the canonical MASE (Hyndman & Koehler 2006) divides by the in-sample one-step naive error, not the evaluation-sample MAE. Under the current definition, the random walk should always equal 1.0 — but it doesn't in the tables. Either the definition is wrong, the denominator is different, or the table values are mislabeled.

**Action:** Audit the actual MASE computation in `src/prepare.py`. Fix the formula or the text to match. Recompute all MASE tables if needed. This affects the 6.8% improvement claim.

**Priority:** Must-do. Everything depends on this metric.

---

### R2.2. Aggregate "average RMSE across targets" is meaningless — CRITICAL

**Problem (GPT-DR, GPT-Pro):** Tables 2, 3, 4 headline "average RMSE across targets" but the targets have different units (CPI is a percentage rate, industrial production is an index, unemployment is a rate). Averaging these is not interpretable.

**Action:** Switch all headline tables to MASE (scale-free). Keep per-variable RMSE in the appendix. Recompute all summary rows using corrected MASE.

**Priority:** Must-do.

---

### R2.3. Report full Diebold-Mariano tests — CRITICAL

**Problem (all 3):** "DM tests not tabulated for brevity" is unacceptable. The paper makes claims about relative performance without statistical evidence.

**Action:** Add a DM test table in the appendix. Pairwise: each method vs random walk, for each variable × horizon on the test era. Use Harvey-Leybourne-Newbold small-sample correction. Report stars for significance. The infrastructure already exists in `evaluate.py`.

**Priority:** Must-do.

---

### R2.4. Proper Bayesian VAR baseline — HIGH

**Problem (GPT-DR, GPT-Pro):** The current VAR is a frequentist VAR with agent-selected covariates. Two issues: (1) it imports the agent's potentially overfit covariate selection, and (2) it lacks shrinkage/regularization. Need a BVAR with Minnesota priors using the full information set.

**Action:** Replace the current VAR baseline with a proper Minnesota BVAR. Use the `bvartools` package or implement Minnesota prior manually. The BVAR should use all 14 covariates (not just the agent's 4) — the Minnesota prior handles dimensionality via shrinkage. Run on both eras.

**Priority:** High. Addresses the "unfair comparison" critique more properly than the current VAR.

---

### R2.5. Remove "Preliminary and incomplete" label

**Problem (all 3):** Still present. Incompatible with submission.

**Action:** Remove from title page. Fill remaining TODOs.

**Priority:** Must-do.

---

## New items from Round 2

### R2.6. Clarify Chronos-2 covariate handling — CRITICAL

**Problem (GPT-DR):** The paper doesn't specify whether covariates are provided as past-only or known-future. For macro covariates like policy rate and US CPI, future values are NOT known at the forecast origin. If Chronos-2 receives future covariate values, this is data leakage.

**Action:** Audit the AutoGluon Chronos-2 implementation. Document explicitly:
- Are covariates provided as past-only (values up to origin t)?
- Does the model internally forecast covariates forward?
- Add a paragraph in the methodology section specifying this.

**Priority:** Must-do. A leakage finding would invalidate the results.

---

### R2.7. Domain-blind prompt experiment — HIGH

**Problem (Gemini-DR, GPT-Pro):** The search agent receives Norwegian-specific domain hints ("oil is important", "exchange rates matter"). The "discovery" of oil and policy rate as covariates may be prompt-guided, not truly autonomous.

**Action:** Create `configs/program_blind.md` with generic instructions (no country-specific hints). Run 50 iterations with the blind prompt. Compare:
- Does the agent still find oil/policy_rate?
- Does it find a different (better? worse?) configuration?
- How does the blind config perform on the test era?

This directly tests whether LLM reasoning adds value beyond prompt engineering.

**Priority:** High. Strengthens the "agentic discovery" claim if covariates are re-discovered without hints.

---

### R2.8. Probabilistic evaluation (CRPS) — HIGH

**Problem (Gemini-DR, GPT-DR):** Chronos-2 produces quantile forecasts, but evaluation is point-only. The agent-tuned config might have better uncertainty calibration (wider intervals during crises) invisible in RMSE/MASE.

**Action:** Extract quantile forecasts from Chronos-2 (AutoGluon returns quantile columns). Compute:
- CRPS (Continuous Ranked Probability Score)
- Pinball loss at τ = {0.1, 0.25, 0.5, 0.75, 0.9}
- Prediction interval coverage (90%, 50%)

Add a subsection in results and an appendix table.

**Priority:** High for IJF. Foundation models' key advantage is probabilistic output.

---

### R2.9. Rolling validation window experiment — MEDIUM-HIGH

**Problem (Gemini-DR, GPT-Pro):** The static 2006-2015 validation window is the root cause of overfitting. Would results improve if the search re-ran periodically with updated validation windows?

**Action:** Implement a "rolling search" experiment:
- At 2016-01: search on 2006-2015, freeze config for 2016-2018
- At 2019-01: re-search on 2009-2018, freeze config for 2019-2021
- At 2022-01: re-search on 2012-2021, freeze config for 2022+
- Compare test-era performance against the static search

This tests whether periodic re-optimization mitigates the overfitting. If the agent drops policy_rate after 2022 (when the rate regime changed), that's a strong finding.

**Priority:** Medium-high. Directly addresses the core overfitting mechanism.

---

### R2.10. Ablation: leave-one-out covariates — MEDIUM

**Problem (GPT-Pro):** The current ablation is path-dependent (sequential). The policy rate's +14.1% gap depends on it being added after brent_crude. Need leave-one-out decomposition.

**Action:** For the final best config (4 covariates + ctx96 + LoRA), run:
- Drop brent_crude only
- Drop policy_rate only
- Drop us_cpi only
- Drop nok_eur only

Compare test-era MASE for each. This shows which covariate is most harmful independent of ordering.

**Priority:** Medium. Strengthens the ablation story.

---

### R2.11. Reproducibility package — MEDIUM

**Problem (GPT-DR, GPT-Pro):** Need full software versions, exact prompts, complete search logs.

**Action:**
- Add `paper/reproducibility/` with: program.md (full prompt), software versions, search_log.jsonl, data retrieval instructions
- Add exact Chronos-2 checkpoint, AutoGluon version, Claude model version to the paper
- Add a "Replication" appendix with these details

**Priority:** Medium. Required for IJF but doesn't require new experiments.

---

### R2.12. Bayesian optimization comparison — MEDIUM

**Problem (Gemini-DR):** Random search is too weak a baseline. Modern AutoML uses Bayesian optimization.

**Action:** Implement TPE (Tree-structured Parzen Estimator) search using `optuna`. Same search space, same evaluation protocol, same 50-iteration budget.

**Priority:** Medium. Would strengthen the LLM vs standard AutoML comparison, but random search already makes the point.

---

## Explicitly out of scope for this revision

- **True real-time data vintages** — acknowledged as limitation; SSB vintage access not available
- **Second foundation model** (TimesFM, Moirai) — large engineering effort, mention in future work
- **Second country** — acknowledged; mention Canada/Sweden as future extensions
- **TVP-VAR or dynamic model averaging** — complex implementation for a comparison that may not change the story
- **Multiple LLM search runs with different seeds** — Claude API is expensive; acknowledge stochasticity as limitation

---

## Implementation priority

| # | Task | Type | Effort | Impact |
|---|------|------|--------|--------|
| 1 | Fix MASE definition + recompute (R2.1) | Code fix | Small | Critical |
| 2 | Switch tables to MASE headlines (R2.2) | Paper edit | Small | Critical |
| 3 | Full DM test table (R2.3) | Code + paper | Medium | Critical |
| 4 | Audit covariate handling (R2.6) | Investigation | Small | Critical |
| 5 | Remove "preliminary" + fill TODOs (R2.5) | Paper edit | Small | Must-do |
| 6 | Proper Minnesota BVAR (R2.4) | Code + experiments | Medium | High |
| 7 | Domain-blind search (R2.7) | Experiments | Medium | High |
| 8 | CRPS / probabilistic eval (R2.8) | Code + experiments | Medium | High |
| 9 | Leave-one-out ablation (R2.10) | Experiments | Small | Medium |
| 10 | Rolling validation search (R2.9) | Code + experiments | Large | Medium-high |
| 11 | Reproducibility appendix (R2.11) | Documentation | Small | Medium |
| 12 | Bayesian optimization comparison (R2.12) | Code + experiments | Medium | Medium |
