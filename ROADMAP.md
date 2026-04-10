# ROADMAP — Automated Feature Engineering for Macro Forecasting

> **Status:** Superseded — see `paper/REVISION-PLAN-4.md` for current execution spec
> **Last updated:** 2026-04-10
> **Collaborators:** Vegard Larsen, Leif Anders Thorsrud

> **Note (2026-04-10):** Phases 0-5 below described the original Norway-only plan and are all complete. The project is now executing `paper/REVISION-PLAN-4.md`, which targets the International Journal of Forecasting with a three-country evaluation (Norway + Canada + Sweden). This ROADMAP is retained as a historical record; see `STATUS.md` for current progress against the revision plan.

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

**Deliverable:** Baseline results table. ARIMA is the best classical baseline. Zero-shot Chronos-2 (120M) is competitive at h=1 but falls behind at longer horizons.

---

## Phase 2: Manual fine-tuning — not started

**Goal:** Understand what economy-specific fine-tuning buys over zero-shot.

- [ ] Manual covariate selection (theory-driven, Vegard + Leif pick)
- [ ] LoRA fine-tuning of amazon/chronos-2 (120M) on Norwegian data
- [ ] Manual hyperparameter tuning (fine_tune_lr, LoRA rank, context length)
- [ ] Compare against Phase 1 baselines
- [ ] Document which choices matter most

**Deliverable:** Manually tuned Chronos-2 results. This is the "expert benchmark" the agent must beat.

---

## Phase 3: Search loop — first experiment complete

**Goal:** Build and run the agentic outer-loop search.

- [x] Implement search.py — LLM-guided outer loop controller
- [x] Define search space in configs/ (search_space.yml)
- [x] Write program.md agent instructions
- [x] Implement train.py scaffold (amazon/chronos-2, 120M)
- [x] **Run search loop on validation era** — 50 iterations, 6.8% MASE improvement
- [x] Log all experiments for reproducibility (results/search_log.jsonl)
- [x] Analyze: agent discovered brent_crude + policy_rate + us_cpi as optimal covariates
- [ ] Compare against Phase 2 manual pipeline
- [ ] Run more iterations (fine-tuning exploration)

**Deliverable:** Agent-selected pipeline: `covariates=[brent_crude, policy_rate, us_cpi, nok_eur], context_length=96, LoRA fine-tune (100 steps, 5e-6)`. MASE improved from 1.94 to 1.81 (6.8%).

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

## Phase 5: Frozen test evaluation — done

**Goal:** Final results on held-out test period (2016+).

- [x] Lock the pipeline from Phase 3 (no further search)
- [x] Evaluate on 2016-01 onward
- [ ] Report by subperiod: 2016-19, 2020-21 (COVID), 2022+ (inflation/Ukraine)
- [x] All metrics, all horizons
- [x] Compare all methods side by side

**Deliverable:** Final results table. Key finding: agent-tuned config overfits to validation era; zero-shot Chronos-2 is more robust to test-era regime changes than ARIMA.

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

- [x] Draft Norway-only manuscript
- [x] Three rounds of AI-referee review (see `paper/ai-referee-reports/round-{1,2,3}/`)
- [ ] Three-country rewrite (see `paper/REVISION-PLAN-4.md`, Phase 6)
- [ ] Internal review (Vegard + Leif)
- [ ] Circulate to colleagues for feedback
- [ ] Submit to International Journal of Forecasting

**Target journal:** International Journal of Forecasting (locked as of 2026-04-01; see REVISION-PLAN-4 §2)

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
