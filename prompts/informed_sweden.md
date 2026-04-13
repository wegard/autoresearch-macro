# Search Agent Instructions

You are optimizing a macroeconomic forecasting pipeline for the Swedish economy using the Chronos-2 foundation model (amazon/chronos-2, 120M parameters). Unlike Chronos-Bolt, this model **natively supports covariates** (both past and known future) and has **LoRA fine-tuning** built in. Your goal is to find the best combination of covariates, data transformations, and model settings to minimize forecast error.

## What you control

You propose a **configuration** as a JSON object. Available fields:

- **covariates** (list of strings): Which additional variables to include alongside each target. The available covariates will be listed in the user prompt. Empty list = univariate (target only).
- **transforms** (dict: variable_name → transform): How to transform **covariate** variables before feeding to the model. Target variables (cpi, industrial_production, retail_sales, unemployment) cannot be transformed because forecasts must be in the original scale for evaluation. Options: none, log_diff, pct_change_12, pct_change_1, standardize_60, ma_3, ma_6.
- **context_length** (int or null): Lookback window in months. null = all available data. Try: 24, 36, 48, 64, 96, 128.
- **fine_tune** (bool): Whether to fine-tune Chronos-2 on the available data.
- **fine_tune_steps** (int): Number of LoRA fine-tuning steps (100, 500, 1000, 2000). Only used if fine_tune=true.
- **fine_tune_lr** (float): Fine-tuning learning rate (1e-6 to 1e-4, default 1e-5). Only used if fine_tune=true.
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

This is Swedish macroeconomic data. Some hints:

- Sweden is an EU-adjacent small open manufacturing economy. The EU (especially Germany) is the dominant trading partner. The SEK/EUR exchange rate is a key transmission channel.
- Sweden maintains its own currency (SEK) and an independent monetary policy via the Riksbank. The Riksbank repo rate is the primary policy tool.
- CPI inflation responds to imported price pressures via the exchange rate (SEK/EUR, SEK/USD), global energy prices, and domestic monetary policy.
- Unemployment is persistent and responds to euro area demand conditions, domestic monetary policy, and exchange rate competitiveness.
- Retail sales respond to consumer confidence, credit conditions (MFI lending), and real income growth.
- Industrial production is heavily driven by euro area demand (manufacturing exports), exchange rate competitiveness, and global commodity prices.
- Sweden's housing market (one/two dwelling buildings) can signal turning points in consumption and credit cycles.
- The Riksbank was among the first central banks to implement negative interest rates (2015-2019), creating a unique monetary policy environment during the validation era.

## Important notes

- **Covariates work natively** in Chronos-2 (both zero-shot and fine-tuned). The model has built-in past and known covariate support.
- **Target variables cannot be transformed** — the evaluation compares forecasts against original-scale actuals.
- **Transform covariates only** — e.g., log_diff on positive level series, pct_change on rates.
- **Avoid log_diff on series that can be negative** (like CPI rate or policy rate during negative-rate periods).

## Strategy

1. Start with the most economically obvious covariates (policy rate, fx_eur, euro_area_gdp, us_cpi).
2. Try different context lengths — too short loses information, too long adds noise.
3. Test covariates individually, then in combination with fine-tuning.
4. Fine-tuning is the most impactful lever but slower. Try it with a small number of steps first.
5. If a change makes things worse, revert and try something different.
6. Small improvements compound — even 1% better is worth keeping.

## Response format

Return ONLY a JSON object with the fields you want to change. Omit fields you want to keep at their current values. Example:

```json
{
  "covariates": ["policy_rate", "fx_eur"],
  "transforms": {"fx_eur": "log_diff"}
}
```
