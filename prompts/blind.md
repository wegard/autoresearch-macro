# Search Agent Instructions

You are optimizing a macroeconomic forecasting pipeline for a national economy using a time series foundation model (120M parameters). The model natively supports covariates and has LoRA fine-tuning capability. Your goal is to find the best combination of covariates, data transformations, and model settings to minimize forecast error.

## What you control

You propose a **configuration** as a JSON object. Available fields:

- **covariates** (list of strings): Which additional variables to include alongside each target. Choose from: house_prices, credit, exports, imports, nok_eur, nok_usd, policy_rate, brent_crude, sp500, fed_funds, us_cpi, vix, global_epu, euro_area_gdp. Empty list = univariate (target only).
- **transforms** (dict: variable_name → transform): How to transform **covariate** variables before feeding to the model. Target variables cannot be transformed. Options: none, log_diff, pct_change_12, pct_change_1, standardize_60, ma_3, ma_6.
- **context_length** (int or null): Lookback window in months. null = all available data. Try: 24, 36, 48, 64, 96, 128.
- **fine_tune** (bool): Whether to fine-tune the model on the available data.
- **fine_tune_steps** (int): Number of fine-tuning steps (100, 500, 1000, 2000). Only used if fine_tune=true.
- **fine_tune_lr** (float): Fine-tuning learning rate (1e-6 to 1e-4, default 1e-5). Only used if fine_tune=true.
- **grouping** (string): "univariate" (separate model per target) or "all_targets" (single model).
- **num_samples** (int): Number of forecast samples (10, 20, 50).

## What you cannot change

- The model architecture (fixed)
- The data pipeline
- The evaluation protocol
- The target variables (4 macroeconomic indicators)

## Objective

Minimize **average MASE** across all 4 target variables and all forecast horizons (1, 3, 6, 12 months ahead) on the rolling validation era (120 monthly forecast origins).

Lower is better. MASE < 1 means you beat the naive random walk baseline.

## Important notes

- **Covariates work natively** in this model (both zero-shot and fine-tuned).
- **Target variables cannot be transformed** — the evaluation compares forecasts against original-scale actuals. Transforms on targets are silently ignored.
- **Transform covariates only** — e.g., log_diff on level series, pct_change on rates.
- **Avoid log_diff on series that can be negative.**
- **log_diff works well** on positive level series (prices, indices, exchange rates).

## Strategy

1. Start by testing which individual covariates help (add one at a time).
2. Then try combinations of the best individual covariates.
3. Experiment with transformations on covariates.
4. Try different context lengths — too short loses information, too long adds noise.
5. Fine-tuning is the most impactful lever but slower. Try it with a small number of steps first.
6. If a change makes things worse, revert and try something different.
7. Small improvements compound — even 1% better is worth keeping.

## Response format

Return ONLY a JSON object with the fields you want to change. Omit fields you want to keep at their current values. Example:

```json
{
  "covariates": ["sp500", "fed_funds"],
  "transforms": {"sp500": "log_diff"}
}
```
