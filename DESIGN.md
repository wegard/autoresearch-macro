# Automated Feature Engineering for Macro Forecasting

**Status:** Idea
**Collaborators:** Vegard, Leif Anders Thorsrud
**Origin:** Karpathy's autoresearch + Amazon's Chronos-2
**Date:** 2026-03-27

## Research question

Can an agentic outer-loop search procedure improve pseudo-real-time forecasts of the Norwegian macroeconomy by selecting data representations, covariates, and fine-tuning settings — relative to zero-shot foundation models, manually tuned models, and standard macro forecasting baselines?

## Core idea

Use an autoresearch-style outer loop to search over task design, data construction, covariates, transformations, and fine-tuning choices for time series foundation models. The agent doesn't touch model architecture — it searches over the forecasting pipeline.

The contribution is **not** "an agent found a better model." It is:
- Evaluation of universal time-series foundation models in a small open economy macro setting
- Disciplined pseudo-real-time evidence on zero-shot vs fine-tuned performance
- Evidence on whether agentic search can improve task construction and model adaptation under realistic forecasting protocols

## Why Norway

Norway is a perfect test case: small open commodity-exporting economy with excellent data availability (SSB, Norges Bank), clear exposure to global shocks (oil, trade), and well-studied by existing macro forecasting literature. Connects to existing work (Components of Uncertainty used topic models to create macro indicators; this uses automated search to discover which indicators matter).

## Hypotheses

- **H1:** Zero-shot foundation models improve on standard benchmarks for some Norwegian macro series, especially when covariates are informative
- **H2:** Light economy-specific fine-tuning improves on zero-shot performance
- **H3:** An agentic search loop over data representation and fine-tuning settings improves on manually specified pipelines
- **H4:** Most gains come from task design and covariate selection rather than unrestricted model rewriting

## Forecasting task

**Starting point: monthly macro panel.** Target variables include inflation, unemployment, industrial production, retail sales, credit, exchange rate, house prices, oil-related variables, confidence indicators.

Quarterly (GDP, consumption, investment) and mixed-frequency are natural extensions but add complexity. Start monthly.

**Horizons:** 1, 3, 6, 12 months ahead.

## Agent search space

The outer loop searches over (preserving interpretability):
- Target variable set
- Covariate selection from a broad pool
- Data transformations (levels, differences, logs, moving averages, lags)
- Context length / lookback window
- Forecast horizon
- Grouping strategy for multivariate tasks
- Zero-shot vs LoRA vs full fine-tuning
- Fine-tuning hyperparameters (LoRA rank, learning rate, etc.)
- Ensembling rules
- Data-window rules (expanding vs rolling)

**Constraint:** Fixed compute budget per iteration (~5 min). Agent logs all experiments for reproducibility.

## Covariate pool

Norwegian:
- SSB macro series (GDP components, employment, CPI, trade, retail, industrial production)
- Norges Bank policy rate, credit indicators
- House prices, confidence surveys
- Text-based indicators (uncertainty, sentiment — from our existing work)

Global:
- Brent crude oil prices
- NOK/EUR, NOK/USD exchange rates
- S&P 500, European GDP growth
- Fed funds rate, ECB rate
- Global uncertainty measures

## Evaluation design

### Rolling pseudo-out-of-sample (critical)

**Phase A — Search/development:**
- Initial estimation sample: earliest available to 2005-12
- Validation era: 2006-01 to 2015-12
- Rolling forecast origins within validation era
- Agent scored on average validation performance across many origins, with penalty for instability/complexity

**Phase B — Frozen final test:**
- Lock the full pipeline (no further search or tuning)
- Evaluate on 2016-01 onward
- Report subperiod results: 2016-19, 2020-21 (COVID), 2022+ (inflation/Ukraine)

### Pseudo-real-time data discipline

At each forecast origin:
- Only use data available at that date
- Respect publication lags
- Do not use revised future vintages if avoidable
- Document clearly if pseudo-real-time rather than true real-time

Without this, the study is much weaker.

### Metrics

Point forecasts:
- RMSE, MAE
- MASE for cross-series comparability

Probabilistic forecasts (Chronos-2 is probabilistic):
- Pinball loss / weighted quantile loss
- Prediction interval coverage

All reported horizon-specific (1, 3, 6, 12 months) and by subperiod.

## Baselines

Four classes — essential for decomposing where gains come from:

1. **Naïve:** random walk, seasonal naïve
2. **Classical univariate:** AR, ARIMA, ETS
3. **Panel/macro benchmarks:** factor model, VAR/BVAR, direct regression with covariates
4. **Foundation model ladder:**
   - Zero-shot Chronos-2 (no covariates)
   - Zero-shot Chronos-2 (with covariates, manual selection)
   - Fine-tuned Chronos-2 (manual pipeline)
   - Fine-tuned Chronos-2 (agentic pipeline)

### Three-way ablation

Isolate:
1. Gain from the foundation model itself (vs classical baselines)
2. Gain from economy-specific fine-tuning (vs zero-shot)
3. Gain from agentic search (vs manually specified pipeline)

Without this decomposition, any improvement is uninterpretable.

## Model scope: Chronos-2-first or model-agnostic?

**Option A (tighter paper):** Focus on Chronos-2 specifically. It has native covariate support via group attention, probabilistic output, and available fine-tuning tooling. The paper becomes "agentic adaptation of Chronos-2 for Norwegian macro."

**Option B (stronger contribution):** Run the same outer loop against multiple foundation models (Chronos-2, TimesFM, Lag-Llama) plus baselines. Tests whether automated pipeline search generalizes across approaches. Harder to execute but more publishable.

**Recommendation:** Start with Option A, design for Option B. Build the search loop model-agnostic from day one, but present initial results on Chronos-2.

## Technical setup

### Repository structure
1. **`prepare.py` (locked):** Downloads SSB/FRED data, handles vintages and publication lags, formats into standardized panel
2. **`train.py` (agent sandbox):** Loads foundation model, agent edits covariate selection, transformations, fine-tuning config
3. **`program.md` (instructions):** Constrains agent to data pipeline and fine-tuning only, 5-min budget, optimize rolling validation metric
4. **`evaluate.py` (locked):** Frozen evaluation on test period, all metrics

### Technical note
- Use `chronos-forecasting>=2.1.0` (fixes for past-only covariates during fine-tuning)
- AutoGluon-TimeSeries as the interface layer
- Build an autoresearch-for-forecasting framework, not a direct port of Karpathy's repo

## Open questions

- Mixed-frequency: worth the complexity for v1?
- True real-time vintages — does Norges Bank or SSB provide vintage databases?
- How to handle the agent discovering spurious correlations that work in-sample?
- Publication target: J. Applied Econometrics? J. Econometrics? International J. Forecasting?
- Can we include our own text-based indicators as covariates? (Connects to Components of Uncertainty)

## Potential titles

1. Agentic adaptation of foundation models for Norwegian macroeconomic forecasting
2. Can autonomous search improve foundation-model forecasts for small open economies?
3. From zero-shot to economy-specific: automated pipeline search for macro time series
4. Automated feature engineering for macroeconomic forecasting with foundation models
