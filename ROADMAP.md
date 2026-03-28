# ROADMAP — Automated Feature Engineering for Macro Forecasting

> **Status:** Active
> **Last updated:** 2026-03-28
> **Collaborators:** Vegard Larsen, Leif Anders Thorsrud

---

## Phase 0: Setup and data — done

**Goal:** Working data pipeline, verified pseudo-real-time discipline, baseline forecasts.

- [x] Project workspace created
- [x] Research design drafted (DESIGN.md)
- [x] Autoresearch repo cloned for reference
- [x] prepare.py spec written (PREPARE-SPEC.md)
- [x] Verify SSB table IDs and publication lags (verified 2026-03-28 against live API)
- [x] Get FRED API key
- [x] Implement prepare.py (1237 lines, 36 tests)
- [x] Test pseudo-real-time discipline (no leakage detected)
- [ ] Decide on variable panel with Leif
- [x] Verify data coverage (18 variables, 1947-2026, see STATUS.md for gaps)

**Deliverable:** `MacroPanel` object that serves pseudo-real-time data for any forecast origin.

---

## Phase 1: Baselines — done

**Goal:** Establish performance of standard methods on the Norwegian monthly macro panel.

- [x] Naive baselines (random walk, seasonal naive)
- [x] Classical univariate (AR, ARIMA, ETS) per variable
- [ ] Panel/macro benchmarks (factor model, VAR/BVAR) — deferred
- [x] Zero-shot Chronos-2 (no covariates)
- [ ] Zero-shot Chronos-2 (with manual covariate selection)
- [x] Rolling evaluation on validation era (2006-2015)
- [x] Collect all metrics: RMSE, MAE, MASE
- [x] Results by horizon (1, 3, 6, 12 months)

**Deliverable:** Baseline results table. ARIMA is the best classical baseline. Zero-shot Chronos-2 does not beat it.

---

## Phase 2: Manual fine-tuning — not started

**Goal:** Understand what economy-specific fine-tuning buys over zero-shot.

- [ ] Manual covariate selection (theory-driven, Vegard + Leif pick)
- [ ] LoRA fine-tuning of Chronos-2 on Norwegian data
- [ ] Manual hyperparameter tuning (learning rate, LoRA rank, context length)
- [ ] Compare against Phase 1 baselines
- [ ] Document which choices matter most

**Deliverable:** Manually tuned Chronos-2 results. This is the "expert benchmark" the agent must beat.

---

## Phase 3: Search loop — infrastructure ready, experiments pending

**Goal:** Build and run the agentic outer-loop search.

- [x] Implement search.py — LLM-guided outer loop controller (557 lines, 16 tests)
- [x] Define search space in configs/ (search_space.yml)
- [x] Write program.md agent instructions
- [x] Implement train.py scaffold (478 lines, 12 tests)
- [ ] **Run search loop on validation era** (see EXPERIMENT-1.md)
- [ ] Log all experiments for reproducibility
- [ ] Analyze: which configurations does the agent discover?
- [ ] Compare against Phase 2 manual pipeline

**Deliverable:** Agent-selected pipeline. Full experiment log.

---

## Phase 4: Ablation and analysis

**Goal:** Decompose where gains come from.

- [ ] Three-way ablation: (1) foundation model, (2) fine-tuning, (3) agentic search
- [ ] Analyze agent's search trajectory — what did it try, what worked?
- [ ] Test whether agent-discovered covariates are economically interpretable
- [ ] Stability analysis: does the agent find similar pipelines across different seeds?
- [ ] Sensitivity to search budget (how many iterations needed?)

**Deliverable:** Ablation tables and analysis. Core contribution of the paper.

---

## Phase 5: Frozen test evaluation

**Goal:** Final results on held-out test period (2016+).

- [ ] Lock the pipeline from Phase 3 (no further search)
- [ ] Evaluate on 2016-01 onward
- [ ] Report by subperiod: 2016-19, 2020-21 (COVID), 2022+ (inflation/Ukraine)
- [ ] All metrics, all horizons
- [ ] Compare all methods side by side

**Deliverable:** Final results table for the paper.

---

## Phase 6: Extensions (if results warrant)

**Goal:** Strengthen the contribution or broaden scope.

- [ ] Model-agnostic: run same search loop on TimesFM, Lag-Llama
- [ ] Mixed-frequency: add quarterly GDP nowcasting
- [ ] Text-based covariates: include uncertainty/sentiment measures from our existing work
- [ ] True real-time vintages (if SSB/Norges Bank provides them)
- [ ] Longer horizons or density forecasting

---

## Phase 7: Paper

**Goal:** Write and submit.

- [ ] Draft introduction and literature review
- [ ] Write methodology section
- [ ] Create all tables and figures
- [ ] Write results and discussion
- [ ] Internal review (Vegard + Leif)
- [ ] Circulate to colleagues for feedback
- [ ] Submit to target journal

**Target journals (in order of ambition):**
1. Journal of Econometrics
2. Journal of Applied Econometrics
3. International Journal of Forecasting

**Working paper series:** CESifo or Norges Bank WP

---

## Timeline (tentative)

| Phase | Target | Notes |
|-------|--------|-------|
| 0: Data | April 2026 | Done |
| 1: Baselines | May 2026 | Done |
| 2: Manual tuning | June 2026 | Expert benchmark |
| 3: Search loop | July–Aug 2026 | Core experiment, needs GPU time |
| 4: Ablation | Sep 2026 | Analysis |
| 5: Test eval | Oct 2026 | Final numbers |
| 6: Extensions | Nov 2026 | If warranted |
| 7: Paper | Dec 2026–Feb 2027 | Writing and submission |

---

## Compute requirements

- **Phase 0-2:** Laptop or single GPU. Data download + classical baselines + initial fine-tuning.
- **Phase 3:** Needs sustained GPU time. Vegard's workstation (dual RTX 4090) or cloud. Overnight search loops (~12 experiments/hour × 8 hours = ~100 experiments per night).
- **Phase 4-5:** Moderate — evaluation runs on locked pipeline.
- **Phase 6:** More GPU time if running multiple foundation models.

---

## Key risks

1. **SSB data gaps:** Industrial production ends 2023M12 — table may be discontinued
2. **Chronos-2 fine-tuning fragility:** LoRA on small macro datasets might not help
3. **Agent finds nothing:** Agentic search might not beat manual tuning — that's still a publishable result (negative is informative)
4. **Pseudo-real-time complexity:** Publication lag handling is fiddly and easy to get wrong
5. **Compute cost:** Extended search loops on foundation models are GPU-hungry
