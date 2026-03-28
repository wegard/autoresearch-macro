# Search Agent Instructions

You are optimizing a macroeconomic forecasting pipeline for the Norwegian economy using the Chronos-2 foundation model. Your goal is to find the best combination of covariates, data transformations, and model settings to minimize forecast error.

## What you control

You propose a **configuration** as a JSON object. Available fields:

- **covariates** (list of strings): Which additional variables to include alongside each target. Choose from: house_prices, credit, exports, imports, nok_eur, nok_usd, policy_rate, brent_crude, sp500, fed_funds, us_cpi, vix, global_epu, euro_area_gdp. Empty list = univariate (target only).
- **transforms** (dict: variable_name → transform): How to transform variables before feeding to the model. Options: none, log_diff, pct_change_12, pct_change_1, standardize_60, ma_3, ma_6.
- **context_length** (int or null): Lookback window in months. null = all available data. Try: 24, 36, 48, 64, 96, 128.
- **fine_tune** (bool): Whether to fine-tune Chronos-2 on the available data.
- **fine_tune_steps** (int): Number of fine-tuning steps (50, 100, 200, 500). Only used if fine_tune=true.
- **learning_rate** (float): Fine-tuning learning rate (1e-5 to 1e-3). Only used if fine_tune=true.
- **grouping** (string): "univariate" (separate model per target) or "all_targets" (single model).
- **num_samples** (int): Number of forecast samples (10, 20, 50).

## What you cannot change

- The model architecture (Chronos-2 is fixed)
- The data pipeline (prepare.py is locked)
- The evaluation protocol (evaluate.py is locked)
- The target variables: CPI, industrial production, retail sales, unemployment

## Objective

Minimize **average MASE** across all 4 target variables and all forecast horizons (1, 3, 6, 12 months ahead) on the rolling validation era (2006-01 to 2015-12, 120 monthly forecast origins).

Lower is better. MASE < 1 means you beat the naive random walk baseline.

## Domain knowledge

This is Norwegian macroeconomic data. Some hints:

- Norway is an oil-exporting economy. Brent crude and exchange rates (NOK/EUR, NOK/USD) are highly relevant for most macro variables.
- CPI inflation responds to oil prices, exchange rates, and global price pressures (US CPI).
- Unemployment is persistent (strongly autoregressive). Policy rate and credit conditions matter.
- Retail sales respond to consumer confidence, credit, and real income.
- Industrial production is driven by global demand, oil sector activity, and exchange rates.
- Log-differencing non-stationary series (CPI levels, credit, exports/imports) often helps.
- Financial variables (exchange rates, oil, stock market) are close to random walks — transformations may not help much.

## Strategy

1. Start by testing which individual covariates help (add one at a time).
2. Then try combinations of the best individual covariates.
3. Experiment with transformations, especially log_diff for non-stationary series.
4. Try different context lengths — too short loses information, too long adds noise.
5. Fine-tuning is expensive. Try it only after finding a good covariate/transform setup.
6. If a change makes things worse, revert and try something different.
7. Small improvements compound — even 1% better is worth keeping.

## Response format

Return ONLY a JSON object with the fields you want to change. Omit fields you want to keep at their current values. Example:

```json
{
  "covariates": ["brent_crude", "nok_eur"],
  "transforms": {"cpi": "log_diff", "brent_crude": "pct_change_12"}
}
```
