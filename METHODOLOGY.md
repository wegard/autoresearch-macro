# Methodology

> Source of truth for the study design. Keep this document up to date when methods change. It will serve as the blueprint for the paper's methodology section.

**Last updated:** 2026-03-29

---

## 1. Research question

Can an LLM-guided search procedure improve pseudo-real-time forecasts of the Norwegian macroeconomy by selecting data representations, covariates, and fine-tuning settings for a time series foundation model — relative to the zero-shot foundation model, classical baselines, and manually tuned pipelines?

## 2. Hypotheses

- **H1:** Zero-shot Chronos-2 improves on classical baselines (AR, ARIMA, ETS) for some Norwegian macro series, especially at short horizons.
- **H2:** Economy-specific adaptation (covariates and/or fine-tuning) improves on zero-shot performance.
- **H3:** LLM-guided search over the pipeline configuration discovers better setups than manual expert selection.
- **H4:** Most gains come from covariate selection and data representation rather than model fine-tuning.

## 3. Data

### 3.1 Sources

| Source | Variables | API |
|--------|-----------|-----|
| Statistics Norway (SSB) | CPI, industrial production, retail sales, house prices, credit, exports, imports, unemployment | JSON-stat2 via `data.ssb.no/api/v0` |
| Norges Bank | NOK/EUR, NOK/USD, key policy rate | SDMX-CSV via `data.norges-bank.no/api/data` |
| Federal Reserve (FRED) | Brent crude, NASDAQ, fed funds rate, US CPI, Euro area GDP, VIX, Global EPU | `fredapi` Python client |

### 3.2 Variable panel

| Variable | Source | Table/Series ID | Frequency | Pub. lag (days) | Available from |
|----------|--------|-----------------|-----------|-----------------|----------------|
| cpi | SSB | 03013 / Tolvmanedersendring | Monthly | 10 | 1979-01 |
| industrial_production | SSB | 14208 / P105 / Sesongjustert | Monthly | 40 | 1990-01 |
| retail_sales | SSB | 07129 / NACE 47 / VolumSesong | Monthly | 30 | 2000-01 |
| house_prices | SSB | 07221 / SesJustBoligindeks | Quarterly → monthly (ffill) | 45 | 2005-03 |
| credit | SSB | 11599 / AarsTrans2 | Monthly | 40 | 1986-12 |
| exports | SSB | 08803 / Etot / All countries | Monthly | 40 | 1988-01 |
| imports | SSB | 08803 / Itot / All countries | Monthly | 40 | 1988-01 |
| unemployment | SSB | 13760 / ArbledProsArbstyrk / S | Monthly | 30 | 2006-01 |
| nok_eur | Norges Bank | EXR / B.EUR.NOK.SP | Daily → monthly (avg) | 1 | 1999-01 |
| nok_usd | Norges Bank | EXR / B.USD.NOK.SP | Daily → monthly (avg) | 1 | 1990-01 |
| policy_rate | Norges Bank | IR / B.KPRA.. | Daily → monthly (avg) | 0 | 1990-01 |
| brent_crude | FRED | DCOILBRENTEU | Daily → monthly (avg) | 1 | 1987-05 |
| sp500 | FRED | NASDAQCOM | Daily → monthly (avg) | 1 | 1971-02 |
| fed_funds | FRED | FEDFUNDS | Monthly | 1 | 1954-07 |
| us_cpi | FRED | CPIAUCSL | Monthly | 15 | 1947-01 |
| euro_area_gdp | FRED | CLVMNACSCAB1GQEA19 | Quarterly → monthly (ffill) | 90 | 1995-01 |
| vix | FRED | VIXCLS | Daily → monthly (avg) | 1 | 1990-01 |
| global_epu | FRED | GEPUCURRENT | Monthly | 30 | 1997-01 |

**Target variables** (4): cpi, industrial_production, retail_sales, unemployment.

**Covariates** (14): All non-target variables.

### 3.3 Pseudo-real-time discipline

At each forecast origin date *t*, only data that would have been publicly available on date *t* is used. For a monthly observation indexed at month-end *m*, the observation is available when:

> month_end(*m*) + publication_lag ≤ *t*

This is enforced by `MacroPanel.available_at(t)` in `src/prepare.py`. The publication lags listed above are approximate and configured in `configs/publication_lags.yml`.

No revised data vintages are used — we use the latest-vintage values throughout but restrict availability by publication lag. This is pseudo-real-time, not true real-time.

### 3.4 Frequency alignment

- Daily series (exchange rates, oil, VIX, NASDAQ) are aggregated to monthly by arithmetic mean.
- Quarterly series (house prices, Euro area GDP) are expanded to monthly by forward-fill (last known value carried forward).
- All series are indexed at end-of-month dates.

## 4. Evaluation protocol

### 4.1 Rolling expanding-window design

For each forecast origin *t* in the evaluation period:
1. Construct the data panel available at *t* (respecting publication lags)
2. Produce point forecasts at horizons *h* ∈ {1, 3, 6, 12} months ahead for each target variable
3. Record the forecasts and compare against realized values

The training window expands with each origin — all data available before *t* is used as context.

### 4.2 Evaluation eras

| Era | Period | Origins | Purpose |
|-----|--------|---------|---------|
| Validation | 2006-01 to 2015-12 | 120 monthly | Model selection, search, hyperparameter tuning |
| Test | 2016-01 onward | ~110 monthly | Final out-of-sample evaluation (frozen, no tuning) |

Test-era subperiods for regime analysis:
- Pre-COVID: 2016-01 to 2019-12
- COVID: 2020-01 to 2021-12
- Post-COVID / inflation: 2022-01 onward

### 4.3 Horizons

All forecasts are direct multi-step: the model produces forecasts for *h* = 1, 3, 6, 12 months ahead simultaneously. Results are reported separately by horizon.

## 5. Metrics

All metrics are computed over the set of forecast origins in the evaluation era.

**Root Mean Squared Error (RMSE):**

> RMSE = sqrt( (1/N) Σ (y_{t+h} - ŷ_{t+h|t})² )

**Mean Absolute Error (MAE):**

> MAE = (1/N) Σ |y_{t+h} - ŷ_{t+h|t}|

**Mean Absolute Scaled Error (MASE):**

> MASE = MAE / MAE_naive

where MAE_naive is the MAE of the random walk (no-change) forecast. MASE < 1 means the method beats the naive baseline. MASE is the primary metric for the search loop because it is scale-independent across target variables.

**Pinball loss** (for probabilistic forecasts): defined but not yet used in the search — available for future extension.

## 6. Baselines

### 6.1 Random walk

Forecast = last observed value at the forecast origin. The simplest possible baseline and the MASE denominator.

### 6.2 Seasonal naive

Forecast *h* months ahead = observation from 12−(*h* mod 12) months before the origin. Captures simple seasonality.

### 6.3 AR(p) — direct regression

For each target variable and horizon, fit an autoregressive model by OLS with lag order *p* selected by BIC over *p* ∈ {1, ..., 12}. The regression is direct (separate model per horizon), not iterated.

### 6.4 ARIMA — AIC order selection

For each target and horizon, fit ARIMA(*p*, *d*, *q*) with order selected by AIC over a grid: *p* ∈ {0, 1, 2, 3}, *d* ∈ {0, 1}, *q* ∈ {0, 1, 2}. Multi-step forecasts produced by the fitted model's `forecast()` method. Falls back to random walk on convergence failure.

### 6.5 ETS — exponential smoothing

Automatic model selection via `statsmodels.tsa.holtwinters.ExponentialSmoothing`. Configurations tried: no trend, additive trend, damped additive trend, with and without additive seasonality (period=12). Best model selected by AIC. Falls back to random walk on failure.

## 7. Foundation model

### 7.1 Model

**amazon/chronos-2** (120M parameters). A universal time series forecasting model based on a transformer architecture, pretrained on billions of time series observations. Reference: Ansari et al. (2025), "Chronos-2: From Univariate to Universal Forecasting."

Key properties:
- Native support for past covariates and known future covariates
- Deterministic point forecasts via a single forward pass
- Maximum context length: 8,192 time steps
- Cross-learning: joint predictions across time series in a batch

### 7.2 Interface

Accessed via AutoGluon TimeSeries (`autogluon.timeseries.TimeSeriesPredictor`) using the `"Chronos-2"` model key. This wraps `Chronos2Pipeline` from the `chronos-forecasting` package.

### 7.3 Fine-tuning

LoRA (Low-Rank Adaptation) fine-tuning is available:
- Target modules: self-attention Q, K, V, O projections + output patch embedding
- Default configuration: rank *r* = 8, α = 16
- Default learning rate: 1 × 10⁻⁵
- Default steps: 1,000

In the current setup, fine-tuning is performed once on the first forecast origin's available data. The fine-tuned model is then reused for all subsequent origins. This fit-once architecture means the fine-tuned model may overfit to early-period data — a known limitation.

## 8. Search procedure

### 8.1 Overview

An LLM (Claude Sonnet via the Anthropic API) proposes pipeline configurations. Each proposal specifies which covariates to include, how to transform them, the context window length, and whether to fine-tune. The proposal is evaluated on the validation era, and accepted or rejected based on whether it improves the best-so-far score.

### 8.2 Search space

| Dimension | Range | Default |
|-----------|-------|---------|
| Covariates | Any subset of 14 available variables | `[]` (none) |
| Covariate transforms | none, log_diff, pct_change_1, pct_change_12, standardize_60, ma_3, ma_6 | `{}` (none) |
| Context length | 24, 36, 48, 64, 96, 128 months, or unlimited | unlimited |
| Fine-tuning | on/off (LoRA) | off |
| Fine-tune steps | 100, 500, 1,000, 2,000 | 1,000 |
| Fine-tune learning rate | 1 × 10⁻⁶ to 1 × 10⁻⁴ (log scale) | 1 × 10⁻⁵ |
| Grouping | univariate, all_targets | univariate |
| Forecast samples | 10, 20, 50 | 20 |

Target variables are never transformed (forecasts must be in the original scale for evaluation).

### 8.3 Two-phase evaluation

To balance speed and accuracy:
1. **Quick evaluation** (20 subsampled origins, fixed seed): ~30 seconds. If the score is worse than the current best, reject immediately.
2. **Full evaluation** (all 120 origins): ~3 minutes. Only triggered when quick evaluation shows improvement. The accept/reject decision is based on the full score.

The baseline is always scored on all 120 origins so comparisons are fair.

### 8.4 LLM prompt

The search agent receives:
- `program.md`: task description, constraints, available parameters, domain knowledge about the Norwegian economy
- Search space definition from `configs/search_space.yml`
- Current best configuration and score
- History of recent iterations (config, score, status)

The agent returns a JSON object with the fields to change. Fields not included are kept at their current values.

### 8.5 Accept/reject

A proposed configuration is accepted if its full-evaluation MASE (averaged across all target variables and horizons) is strictly lower than the current best. The search state is persisted after each iteration and can be resumed.

## 9. Reproducibility

### 9.1 Software

- Python 3.11
- `chronos-forecasting` 2.2.2
- `autogluon.timeseries` 1.5.0
- `torch` 2.9.1 (CUDA 12.8)
- `statsmodels` 0.14.6
- Full dependency lock: `uv.lock`

### 9.2 Hardware

Experiments run on a workstation with NVIDIA GeForce RTX 4090 (24 GB VRAM).

### 9.3 Random seeds

- Origin subsampling uses `numpy.random.default_rng(42)`
- AutoGluon and PyTorch use default seeds (not explicitly controlled)
- Chronos-2 Bolt produces deterministic outputs; original Chronos-2 uses a single forward pass (no sampling)

### 9.4 Data access

All data sources are publicly available and free:
- SSB API: no authentication required
- Norges Bank SDMX: no authentication required
- FRED API: free key from https://fred.stlouisfed.org/docs/api/api_key.html
- Anthropic API: required for the search loop (Claude Sonnet)

---

## 10. Key results

### Validation era (2006-2015)

The search improved Chronos-2 MASE by 6.8% (1.9443 → 1.8129) over 50 iterations. The best config uses 4 covariates (brent_crude, policy_rate, us_cpi, nok_eur), context_length=96, and light LoRA fine-tuning (100 steps, lr=5×10⁻⁶).

### Test era (2016+)

The agent-tuned config does not generalize. Zero-shot Chronos-2 is more robust to the test period's regime changes (COVID pandemic, inflation surge) and beats ARIMA at horizons 3, 6, and 12 months. The random walk is the strongest overall test-era method.

This overfitting finding highlights a fundamental challenge: pipeline optimization on a fixed validation window may not transfer across structural breaks in macroeconomic data.

## Changelog

- **2026-03-29:** Initial version. Documented setup as of the 50-iteration search experiment. Added test-era results showing validation-to-test overfitting.
