# REVISION-PLAN-3

```yaml
plan_version: 3
project_goal: "Turn the current Norway-only manuscript into an International Journal of Forecasting (IJF)-ready three-country paper."
target_journal: "International Journal of Forecasting"
countries:
  - Norway
  - Canada
  - Sweden
primary_claim_working_version: "Agentic search can find economically interpretable validation gains, but those gains may fail to generalize under regime change; zero-shot foundation models can be more robust."
non_negotiables:
  - "Fix all numerical inconsistencies before writing new prose."
  - "Use one authoritative evaluation pipeline for every table and figure."
  - "Maintain pseudo-real-time discipline and publication-lag masking."
  - "Add Canada and Sweden under a harmonized design."
  - "Add stronger econometric and non-LLM search baselines."
  - "Package code and data for IJF reproducibility."
  - "Do not force a positive result. Preserve negative results."
minimum_submission_standard:
  - "Three-country dataset complete and documented."
  - "All main results reproduced from a fresh run."
  - "Random-walk MASE equals 1.000 by construction everywhere."
  - "All manuscript numbers are auto-generated from result files."
  - "Code/data supplement passes a clean rerun on another machine."
```

## 1. Mission

This document is an execution spec for a coding agent.

The current manuscript already contains a publishable idea, but the paper needs to be rebuilt around a stronger and more defensible contribution:

1. The paper must stop looking like a Norway-only proof-of-concept for agentic search.
2. The paper must become a cross-country forecasting evaluation paper aimed at IJF.
3. The central result should be treated as an empirical question, not a foregone conclusion.
4. The likely publishable contribution is not "LLM agents improve macro forecasting." The likely contribution is "agentic search can improve validation performance and produce interpretable pipelines, but those gains are fragile under non-stationarity and often fail out of sample."

## 2. IJF fit and constraints

Design the revision so that it fits IJF explicitly.

### 2.1 Why this paper fits IJF

IJF values forecasting methods, applications, implementation, and evaluation. This project fits best as an empirical forecasting evaluation paper with a methodological angle.

### 2.2 IJF-specific requirements that affect the build

- Use a concise, informative title.
- Keep the abstract in the 100-150 word range.
- Prepare for double-blind review.
- Assume code and data must be shared.
- Assume the paper will be subjected to a reproducibility check.
- Keep main-text tables lean and move extra detail to appendices/online supplement.

### 2.3 Result-framing rule

Do not lock the narrative before the new three-country evidence exists.

Use these decision rules:

- If zero-shot Chronos-2 is most robust in at least 2 of 3 countries, keep the failure-mode / robustness framing.
- If agent-tuned Chronos-2 wins clearly in test-era performance in at least 2 of 3 countries, shift the framing to conditional usefulness of agentic search rather than fragility.
- If results are mixed, frame the paper around heterogeneity across countries and regimes.
- Never claim a general law for all small open economies. Limit the claim to evidence from Norway, Canada, and Sweden.

## 3. Recommended paper framing

### 3.1 Preferred working title

**Agentic Search and the Robustness of Time-Series Foundation Models in Small Open Economies: Evidence from Norway, Canada, and Sweden**

### 3.2 Sharper alternative title if the failure-mode result remains dominant

**When Agentic Search Overfits: Foundation-Model Macroeconomic Forecasting in Norway, Canada, and Sweden**

### 3.3 Primary research questions

1. Are zero-shot foundation models competitive with classical baselines in pseudo-real-time macro forecasting across small open economies?
2. Can agentic search improve validation performance by selecting covariates, context length, and fine-tuning settings?
3. Do those validation gains survive out-of-sample regime changes?
4. Does domain-informed LLM search outperform blind LLM search, random search, greedy stepwise search, and a human economist benchmark?

### 3.4 Core hypotheses to test

- **H1:** Zero-shot Chronos-2 is competitive with strong classical benchmarks across short and medium horizons.
- **H2:** Agentic search improves validation performance relative to zero-shot Chronos-2.
- **H3:** Validation gains from agentic search do not necessarily generalize to the test era.
- **H4:** The generalization gap widens around major regime changes, especially COVID and the post-2022 inflation/tightening period.
- **H5:** Domain-informed prompts find more interpretable pipelines, but not necessarily more robust ones.

## 4. Final empirical design

### 4.1 Countries

Required countries:

- Norway
- Canada
- Sweden

### 4.2 Targets

Use the same four target classes across all countries.

1. **Inflation:** 12-month CPI inflation rate, computed from the raw CPI index for consistency across countries.
2. **Industrial output:** seasonally adjusted monthly industrial/manufacturing activity measure.
3. **Retail sales:** seasonally adjusted monthly retail volume measure.
4. **Unemployment:** seasonally adjusted unemployment rate.

### 4.3 Canada target rule for industrial output

Canada is the one country where the exact analogue of Norway/Sweden industrial production may be less straightforward.

Use this decision order:

1. Preferred: official monthly industrial production / industrial output index if a current, continuous, seasonally adjusted official series exists.
2. Fallback A: official monthly manufacturing/industrial GDP volume series.
3. Fallback B: official real manufacturing sales volume series.

Do not improvise. Document the final choice in `metadata/canada_target_decision.md` with rationale.

### 4.4 Forecast horizons

Keep the original horizon structure:

- 1 month
- 3 months
- 6 months
- 12 months

### 4.5 Forecast origin eras

Use a harmonized origin design across countries.

- **Validation era:** 2006-01 to 2015-12
- **Test era:** 2016-01 to the latest common end date available across all three countries after publication-lag masking

Target common end date:

- First attempt: 2025-03, to stay aligned with the current manuscript
- If one country cannot support this end date cleanly, truncate all three countries to the last common origin for the primary analysis and move longer country-specific tails to an appendix

### 4.6 Test-era subperiods

Use the same subperiod split across all countries:

- **Pre-COVID:** 2016-01 to 2019-12
- **COVID/disruption:** 2020-01 to 2021-12
- **Inflation/tightening:** 2022-01 to common end date

### 4.7 Training window rule

At each forecast origin, use all data available up to that origin, subject to publication-lag masking.

### 4.8 Primary metric

- **Primary:** MASE
- **Secondary:** MAE, RMSE

Enforce this invariant:

- The random walk must equal 1.000 in MASE by construction for every target, horizon, country, and aggregation level.

## 5. Country data plan

### 5.1 High-level source map

| Country | Official macro source | Official central bank / FX source | Global source |
|---|---|---|---|
| Norway | Statistics Norway (SSB) | Norges Bank | FRED / equivalent global public sources |
| Canada | Statistics Canada | Bank of Canada | FRED / equivalent global public sources |
| Sweden | Statistics Sweden (SCB) | Sveriges Riksbank | FRED / equivalent global public sources |

### 5.2 Common covariate template

Retain a search space of roughly the same complexity as the Norway paper, but harmonize it.

Use the following 14-slot template. Country-specific series may differ, but the category structure should stay stable.

1. House prices
2. Credit growth
3. Exports
4. Imports
5. Policy rate
6. FX vs EUR
7. FX vs USD
8. Global oil price
9. NASDAQ or broad US equity index
10. Fed funds rate
11. US CPI
12. VIX
13. Global economic policy uncertainty
14. Partner-area activity variable

### 5.3 Partner-area activity variable rule

Do not force the same partner-area variable mechanically if it makes no economic sense.

Use this mapping:

- **Norway:** euro area activity variable
- **Sweden:** euro area activity variable
- **Canada:** US activity variable

Document the exact series chosen in `metadata/partner_activity_mapping.csv`.

### 5.4 Exchange-rate handling rule

Use country-specific bilateral rates but keep the covariate labels generic.

- Norway: likely NOK/EUR and NOK/USD
- Sweden: likely SEK/EUR and SEK/USD
- Canada: likely CAD/EUR and CAD/USD

Label them in the code as `fx_eur` and `fx_usd` so the search space stays aligned.

### 5.5 Target and covariate metadata requirements

Create one authoritative metadata table:

`metadata/variable_catalog.csv`

Required columns:

- `country`
- `variable_name`
- `role` (`target` or `candidate`)
- `display_name`
- `source_name`
- `source_series_id`
- `source_url`
- `raw_frequency`
- `model_frequency`
- `seasonal_adjustment`
- `publication_lag_days`
- `availability_rule`
- `transform_notes`
- `start_date`
- `end_date`
- `download_script`
- `notes`

## 6. Publication-lag and pseudo-real-time protocol

### 6.1 General rule

For every series, build an availability mask. Do not use a value until it would have been public at the forecast origin.

### 6.2 Norway

Retain the Norway protocol from the current manuscript unless the audit reveals an error.

### 6.3 Canada and Sweden

Do not guess lags casually.

Required procedure:

1. Use official release schedules and release pages.
2. Estimate a conservative fixed lag for each series.
3. Store the chosen lag and the evidence source in metadata.
4. If publication timing changes over time, use a conservative lag that avoids look-ahead bias.
5. For quarterly series, allow forward-filling only after the official release date.

### 6.4 Optional enhancement

If feasible, add an appendix using true real-time/vintage data for Canada for the subset of series where official real-time tables exist.

Do **not** block the main paper on this step.

## 7. Models, benchmarks, and search comparators

### 7.1 Keep the current baseline family

Retain these baseline families, but rebuild them inside the unified evaluation framework:

- Random walk
- Seasonal naive
- AR / direct autoregression
- ARIMA
- ETS
- VAR
- Factor model
- Chronos-2 zero-shot
- Chronos-2 agent-tuned

### 7.2 Add required stronger baselines

These are required for IJF-targeted revision.

1. **BVAR with shrinkage**
   - Minnesota-style shrinkage or equivalent regularized Bayesian VAR
   - Must be competitive and reasonably tuned

2. **Elastic Net direct forecasting**
   - Use lagged target and lagged covariates
   - Tune lag depth and penalty on validation data or a nested pre-validation split

3. **Greedy stepwise search baseline**
   - Deterministic non-LLM search over the same action space
   - This is the main stronger search comparator to random search

### 7.3 Optional high-value baseline

- A second TSFM zero-shot baseline, such as TimesFM or another current universal forecasting model, if implementation is reliable and compute allows

Do not block the core revision on this.

### 7.4 Human economist benchmark

Add one hand-specified benchmark per country.

Process:

1. Before new results are run, the human authors lock one benchmark configuration per country.
2. Each benchmark must specify:
   - covariate set
   - context length
   - whether fine-tuning is used
3. Save these settings in `configs/manual_economist_benchmarks.yaml`.
4. Do not revise the manual benchmark after seeing results.

This benchmark is required to address the critique that the agent may only be rediscovering obvious macroeconomic priors.

### 7.5 Search variants to run

Required search variants for each country:

1. **Informed LLM search**
2. **Blind LLM search**
3. **Random search**
4. **Greedy stepwise search**
5. **Manual economist benchmark**

### 7.6 Minimum search replication budget

Preferred:

- 3 seeds per country for informed LLM search
- 3 seeds per country for blind LLM search
- 3 seeds per country for random search

Minimum fallback if compute is tight:

- 1 seed per country per method, but mark the paper as lower-confidence until additional seeds are added

### 7.7 Search budget fairness rule

Keep the search budget matched as closely as possible across methods.

At minimum, match:

- number of iterations
- quick-evaluation budget
- full-evaluation budget
- allowed action space

## 8. Required decomposition and mechanism checks

### 8.1 Sequential accepted-path ablation

Keep the current sequential ablation logic, but do it for each country and build it automatically from the accepted search path.

### 8.2 Leave-one-component-out ablation

This is required.

For the final best configuration in each country, remove one component at a time:

- each selected covariate
- context truncation
- fine-tuning

This is necessary because sequential ablation is path-dependent.

### 8.3 Fit-once vs periodic re-fit

Retain the current fit-once vs annual re-fit comparison for the final selected pipeline.

### 8.4 Manual vs agent decomposition

Create a decomposition table that isolates the value of:

1. zero-shot base model
2. manual economist covariates
3. LoRA-only adaptation without searched covariates
4. searched covariates without LoRA
5. full searched pipeline

This can live in the appendix if the main text gets crowded.

### 8.5 Multi-window validation robustness

If compute allows, add one robustness exercise where model selection is based on more than one validation block rather than a single fixed 2006-2015 block.

This is high value because it tests whether the current overfitting result is partly caused by single-window selection.

## 9. Statistical evaluation and inference

### 9.1 Granular storage rule

Store per-origin forecast errors in one file:

`results/forecast_errors.parquet`

Required columns:

- `country`
- `target`
- `origin_date`
- `horizon`
- `model_family`
- `model_variant`
- `search_method`
- `seed`
- `run_id`
- `y_true`
- `y_pred`
- `abs_error`
- `sq_error`
- `is_validation`
- `is_test`

### 9.2 Pairwise tests

Required pairwise comparisons:

- Chronos-2 zero-shot vs random walk
- Chronos-2 zero-shot vs ARIMA
- Chronos-2 zero-shot vs BVAR
- Chronos-2 zero-shot vs Chronos-2 agent-tuned
- Chronos-2 agent-tuned vs manual economist benchmark
- Informed LLM best config vs greedy search best config

Use Diebold-Mariano tests with HAC/Newey-West correction appropriate for multi-step horizons.

### 9.3 Reporting rule

Do not rely only on tests versus random walk.

At minimum, report the pairwise comparisons that matter for the paper's actual claims.

### 9.4 Multiple-comparison handling

Primary pairwise tests can be shown unadjusted, but add either:

- a false-discovery-rate correction in the appendix, or
- a significance-count summary with cautionary interpretation

## 10. Reproducibility architecture

This section is mandatory because IJF now expects code/data sharing and performs reproducibility checks.

### 10.1 Repository structure

Use a structure close to this:

```text
project_root/
  data_raw/
  data_interim/
  data_final/
  metadata/
  configs/
  prompts/
  src/
    data/
    features/
    models/
    search/
    evaluation/
    tables/
    figures/
  results/
    forecast_errors.parquet
    model_summaries.csv
    search_logs/
    manifests/
  manuscript/
  tests/
  audit/
  reproducibility/
```

### 10.2 Single source of truth rule

Every main-text number must be derivable from machine-generated result files.

Do not hard-code numbers in the manuscript.

### 10.3 Manifest logging

For every run, save a manifest with:

- code commit hash
- package versions
- model version
- prompt version hash
- seed
- country
- start/end timestamps
- data checksum references

### 10.4 Search logging

Save full search logs, including:

- prompt sent to LLM
- raw LLM response
- parsed JSON config
- quick score
- full score
- accepted/rejected status
- failure message if invalid

### 10.5 Tests to add

Required tests:

1. `test_no_lookahead.py`
2. `test_random_walk_mase_is_one.py`
3. `test_table_generation_is_deterministic.py`
4. `test_search_configs_respect_action_space.py`
5. `test_country_metadata_complete.py`

## 11. Phase-by-phase work plan

### Phase 0 — Freeze and audit the current Norway paper

**Owner:** agent  
**Dependencies:** none

### Tasks

- [ ] Create a frozen repo snapshot before changes.
- [ ] Reproduce the current Norway-only results from code.
- [ ] Compare reproduced values against every table and figure in the PDF.
- [ ] Create `audit/current_discrepancy_report.md`.
- [ ] Identify root causes for mismatches, especially around MASE definitions and table generation.

### Deliverables

- `audit/current_discrepancy_report.md`
- `audit/table_value_crosswalk.csv`

### Acceptance criteria

- Every existing mismatch is either fixed or documented.
- The known trust-breaking inconsistencies are resolved before any new country is added.

### Phase 1 — Refactor into one authoritative evaluation pipeline

**Owner:** agent  
**Dependencies:** Phase 0

### Tasks

- [ ] Centralize metric computation.
- [ ] Centralize pseudo-real-time masking.
- [ ] Centralize forecast error storage.
- [ ] Centralize table generation.
- [ ] Make all tables and figures script-generated.
- [ ] Add tests for determinism and metric identity.

### Deliverables

- `src/evaluation/metrics.py`
- `src/evaluation/availability.py`
- `src/tables/`
- `src/figures/`
- `results/forecast_errors.parquet`

### Acceptance criteria

- Re-running table scripts reproduces the same values exactly.
- Random walk MASE equals 1.000 everywhere.
- No manuscript number exists without provenance.

### Phase 2 — Build the three-country data layer

**Owner:** agent  
**Dependencies:** Phase 1

### Tasks

- [ ] Implement Norway data loader using current codebase.
- [ ] Implement Canada data loader.
- [ ] Implement Sweden data loader.
- [ ] Build common metadata schema.
- [ ] Build availability masks from publication lags.
- [ ] Harmonize target definitions.
- [ ] Harmonize candidate covariate categories.
- [ ] Determine the last common evaluation date.
- [ ] Cache raw downloads and checksums.

### Deliverables

- `metadata/variable_catalog.csv`
- `metadata/publication_lags.csv`
- `metadata/country_sample_windows.csv`
- `metadata/canada_target_decision.md`
- `data_final/panel_{country}.parquet`

### Acceptance criteria

- Each country has a complete monthly panel.
- Every series has source metadata and a lag rule.
- The common evaluation sample is explicit and documented.

### Phase 3 — Implement the baseline suite

**Owner:** agent  
**Dependencies:** Phase 2

### Tasks

- [ ] Rebuild all current baselines inside the unified framework.
- [ ] Add BVAR with shrinkage.
- [ ] Add Elastic Net direct forecasting.
- [ ] Validate VAR/factor implementations.
- [ ] Create manual economist benchmark config file.
- [ ] Add greedy stepwise search baseline.
- [ ] Tune new baselines fairly.

### Deliverables

- `configs/manual_economist_benchmarks.yaml`
- `results/baseline_summary.csv`
- `results/baseline_tuning_log.csv`

### Acceptance criteria

- All baselines run for all countries, targets, and horizons.
- Tuning logic is documented and reproducible.

### Phase 4 — Run search experiments

**Owner:** agent  
**Dependencies:** Phase 3

### Tasks

- [ ] Freeze prompt templates for informed and blind agents.
- [ ] Freeze the action space.
- [ ] Run informed LLM search for each country.
- [ ] Run blind LLM search for each country.
- [ ] Run matched-budget random search.
- [ ] Run matched-budget greedy stepwise search.
- [ ] Save best config per run and best config per country.
- [ ] Evaluate frozen best configs on the test era.

### Deliverables

- `prompts/informed_prompt_template.md`
- `prompts/blind_prompt_template.md`
- `results/search_logs/*.jsonl`
- `results/best_configs.csv`
- `results/search_comparison_summary.csv`

### Acceptance criteria

- Search runs are fully logged.
- Search budgets are comparable.
- Best validation config and test performance are both available for each country and search method.

### Phase 5 — Mechanism and robustness analysis

**Owner:** agent  
**Dependencies:** Phase 4

### Tasks

- [ ] Sequential accepted-path ablation for each country.
- [ ] Leave-one-component-out ablation for each final config.
- [ ] Fit-once vs annual re-fit comparison.
- [ ] Pre-COVID / COVID / inflation-tightening subperiod analysis.
- [ ] Manual benchmark vs agent vs greedy comparison.
- [ ] Optional multi-window validation robustness.
- [ ] Optional Canada true-real-time appendix for selected series.
- [ ] Optional second TSFM baseline.

### Deliverables

- `results/ablation_summary.csv`
- `results/refit_comparison.csv`
- `results/subperiod_summary.csv`
- `results/manual_vs_agent_summary.csv`

### Acceptance criteria

- The paper can support a mechanism section without relying only on path-dependent evidence.

### Phase 6 — Rebuild the manuscript

**Owner:** agent + human authors  
**Dependencies:** Phase 5

### Tasks

- [ ] Rewrite title and abstract.
- [ ] Rewrite introduction around the real contribution.
- [ ] Narrow or support the external-validity claim.
- [ ] Add the three-country data section.
- [ ] Replace all tables and figures with machine-generated versions.
- [ ] Rewrite results to emphasize evaluation, robustness, and heterogeneity.
- [ ] Rewrite discussion to avoid overclaiming.
- [ ] Prepare appendix and online supplement structure.

### Deliverables

- Revised manuscript draft
- Revised appendix
- Revised online supplement

### Acceptance criteria

- The manuscript text matches the generated results exactly.
- The paper reads as an IJF forecasting evaluation paper, not as a tech demo.

### Phase 7 — IJF submission package

**Owner:** agent + human authors  
**Dependencies:** Phase 6

### Tasks

- [ ] Create anonymized manuscript.
- [ ] Create separate title page.
- [ ] Create reproducibility README.
- [ ] Create environment lock file.
- [ ] Run a clean-machine reproduction test.
- [ ] Prepare online supplement folder.
- [ ] Draft any required generative-AI disclosure statement.

### Deliverables

- `reproducibility/README.md`
- `reproducibility/run_all.sh` or equivalent
- anonymized manuscript PDF
- title page file
- archive for code/data supplement

### Acceptance criteria

- A third party can reproduce the main tables and figures from the code/data package.

## 12. Exact tables and figures to target

### Main-text tables

1. **Country/sample design table**
   - countries, targets, start dates, lags, common evaluation window
2. **Baseline performance table**
   - test-era MASE by country and horizon for key methods
3. **Search comparison table**
   - informed LLM vs blind LLM vs random vs greedy vs manual benchmark
4. **Selected pipelines table**
   - covariates, context length, fine-tuning choice by country
5. **Validation-to-test gap table**
   - zero-shot vs searched configs by country
6. **Key pairwise inference table**
   - pairwise DM summaries for central claims

### Main-text figures

1. **Search trajectory figure** by country
2. **Validation vs test scatter/line figure** showing generalization gap across methods
3. **Ablation scissors plot** by country
4. **Subperiod heatmap or line plot** showing robustness across regimes

### Appendix tables

- per-variable results by country
- lag catalog
- metadata catalog
- leave-one-out ablation
- fit-once vs periodic re-fit
- seed-by-seed search results
- manual benchmark settings
- optional second TSFM results

## 13. Manuscript rewrite map

### 13.1 Abstract

Must answer in 100-150 words:

- what is forecasted
- which countries are used
- which methods are compared
- what the main result is
- why it matters for forecasting practice

### 13.2 Introduction

Cut or compress:

- any language implying novelty merely because an LLM agent was used
- any wording that sounds like the paper is about autonomous science rather than forecast evaluation

Add:

- why small open economies matter
- why cross-country evidence matters
- why robustness under non-stationarity matters
- why IJF readers should care in practical forecasting terms

### 13.3 Related literature

Rebalance toward:

- macro forecasting evaluation
- forecast robustness under breaks
- TSFM benchmarking and zero-shot forecasting
- reproducible search/AutoML comparisons

### 13.4 Methods

Make explicit:

- exact availability masking
- exact action space
- exact search budget
- exact tuning rules for strong baselines
- how pairwise tests are done

### 13.5 Results

Recommended order:

1. baseline forecast performance
2. search comparison
3. selected pipelines
4. test-era generalization
5. subperiod breakdown
6. mechanism checks / ablation

### 13.6 Discussion

Discuss:

- robustness vs flexibility
- domain knowledge as help vs trap
- country heterogeneity
- what the results imply for real forecasting workflows

### 13.7 Conclusion

Keep narrow and evidence-matched.

Do not claim that agentic search is broadly ineffective or broadly effective. State what the three-country evidence supports.

## 14. Interpretation guardrails

These are mandatory.

- Do not call the current result a "discovery" unless it survives the new benchmark suite.
- Do not equate validation gains with forecasting gains.
- Do not use one-country evidence to justify a "small open economies" title.
- Do not imply statistical superiority without the relevant pairwise tests.
- Do not hide null or negative results.
- Do not handwave away Canada/Sweden differences; use them.

## 15. Human decisions required

These require author approval and should be surfaced early.

1. Final Canada industrial-output target choice.
2. Final manual economist benchmark configurations.
3. Whether to include a second TSFM baseline in this revision cycle.
4. Whether to include the optional Canada true-real-time appendix.
5. Final title choice after results stabilize.

## 16. Minimum viable paper vs stretch paper

### Minimum viable IJF submission

Required:

- corrected and reproducible Norway results
- Canada and Sweden added
- stronger baselines added
- greedy non-LLM search comparator added
- manual economist benchmark added
- pairwise DM tests for central claims
- full reproducibility package

### Stretch version

Add if time/compute allow:

- second TSFM zero-shot baseline
- multi-window validation selection robustness
- Canada true-real-time appendix
- FDR-adjusted significance appendix
- rolling-correlation / regime-instability visualization for selected covariates

## 17. Execution order summary

Run in this order. Do not skip ahead.

1. Audit current Norway results.
2. Refactor evaluation pipeline.
3. Build Canada/Sweden data layer.
4. Implement stronger baselines.
5. Run search methods.
6. Run robustness/mechanism checks.
7. Rewrite manuscript.
8. Build IJF reproducibility package.

## 18. External official references for the build

Use official sources first.

### IJF

- IJF guide for authors: <https://www.sciencedirect.com/journal/international-journal-of-forecasting/publish/guide-for-authors>
- IJF journal page and reproducibility policy: <https://forecasters.org/ijf/>
- IJF authors page: <https://forecasters.org/ijf/authors/>

### Canada

- Statistics Canada release schedule: <https://www150.statcan.gc.ca/n1/dai-quo/cal2-eng.htm>
- Statistics Canada developers page: <https://www.statcan.gc.ca/en/developers>
- Statistics Canada real-time data tables: <https://www.statcan.gc.ca/en/developers/real-time-data-tables>
- CPI table (seasonally adjusted): <https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000601>
- Retail sales, price, and volume table: <https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2010006701>
- Labour force characteristics table: <https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701>
- Monthly GDP by industry table: <https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610043401>
- Bank of Canada Valet API: <https://www.bankofcanada.ca/valet/>
- Bank of Canada statistics page: <https://www.bankofcanada.ca/rates/>

### Sweden

- Statistics Sweden open data API: <https://www.scb.se/en/services/open-data-api/>
- Statistics Sweden statistical database: <https://www.scb.se/en/statistical-database/>
- CPI page: <https://www.scb.se/en/finding-statistics/statistics-by-subject-area/prices-and-economic-trends/price-statistics/consumer-price-index-cpi/>
- Industrial production index page: <https://www.scb.se/en/finding-statistics/statistics-by-subject-area/business-activities-and-foreign-trade/business-production-sales-and-finances--short-term-statistics/industrial-production-index-ipi/>
- Labour Force Surveys page: <https://www.scb.se/en/finding-statistics/statistics-by-subject-area/labour-market/labour-force-supply/labour-force-surveys-lfs/>
- Riksbank rates/exchange-rate statistics: <https://www.riksbank.se/en-gb/statistics/interest-rates-and-exchange-rates/>
- Riksbank API documentation: <https://www.riksbank.se/en-gb/statistics/interest-rates-and-exchange-rates/retrieving-interest-rates-and-exchange-rates-via-api/>

### Norway

- Keep the existing Norway sources from the current manuscript unless the audit finds a problem.

## 19. Final instruction to the coding agent

Do not optimize for confirming the current story. Optimize for a correct, reproducible, submission-ready forecasting paper.
