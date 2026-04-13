# Audit Report: Paper vs Result Files

Generated automatically by `audit/cross_check_paper.py`.

## 1. Validation Era MASE (tab:validation)

| Method | Horizon | Paper | Result | Status | Diff |
|--------|---------|-------|--------|--------|------|
| random_walk | h=1 | 1.000 | 1.000 | EXACT | 0.0000 |
| random_walk | h=3 | 1.000 | 1.000 | EXACT | 0.0000 |
| random_walk | h=6 | 1.000 | 1.000 | EXACT | 0.0000 |
| random_walk | h=12 | 1.000 | 1.000 | EXACT | 0.0000 |
| arima | h=1 | 0.930 | 0.930 | EXACT | 0.0000 |
| arima | h=3 | 0.983 | 0.983 | EXACT | 0.0000 |
| arima | h=6 | 0.978 | 0.978 | EXACT | 0.0000 |
| arima | h=12 | 1.000 | 0.999 | OK (rounding) | 0.0010 |
| ets | h=1 | 0.964 | 0.953 | MISMATCH | 0.0110 |
| ets | h=3 | 1.002 | 1.011 | MISMATCH | 0.0090 |
| ets | h=6 | 1.013 | 1.013 | EXACT | 0.0000 |
| ets | h=12 | 1.043 | 1.054 | MISMATCH | 0.0110 |
| var | h=1 | 1.000 | 0.999 | OK (rounding) | 0.0010 |
| var | h=3 | 1.063 | 1.063 | EXACT | 0.0000 |
| var | h=6 | 1.119 | 1.119 | EXACT | 0.0000 |
| var | h=12 | 1.133 | 1.133 | EXACT | 0.0000 |
| factor | h=1 | 1.290 | 1.290 | EXACT | 0.0000 |
| factor | h=3 | 1.341 | 1.341 | EXACT | 0.0000 |
| factor | h=6 | 1.520 | 1.520 | EXACT | 0.0000 |
| factor | h=12 | 2.060 | 2.060 | EXACT | 0.0000 |
| chronos2_zs | h=1 | 0.960 | 0.960 | EXACT | 0.0000 |
| chronos2_zs | h=3 | 1.008 | 1.008 | EXACT | 0.0000 |
| chronos2_zs | h=6 | 1.016 | 1.016 | EXACT | 0.0000 |
| chronos2_zs | h=12 | 1.012 | 1.012 | EXACT | 0.0000 |

## 2. Test Era MASE (tab:test)

| Method | Horizon | Paper | Result | Status | Diff |
|--------|---------|-------|--------|--------|------|
| random_walk | h=1 | 1.000 | 1.000 | EXACT | 0.0000 |
| random_walk | h=3 | 1.000 | 1.000 | EXACT | 0.0000 |
| random_walk | h=6 | 1.000 | 1.000 | EXACT | 0.0000 |
| random_walk | h=12 | 1.000 | 1.000 | EXACT | 0.0000 |
| arima | h=1 | 0.977 | 0.977 | EXACT | 0.0000 |
| arima | h=3 | 0.992 | 0.992 | EXACT | 0.0000 |
| arima | h=6 | 1.032 | 1.032 | EXACT | 0.0000 |
| arima | h=12 | 1.029 | 1.029 | EXACT | 0.0000 |
| var | h=1 | 0.979 | 0.979 | EXACT | 0.0000 |
| var | h=3 | 1.075 | 1.075 | EXACT | 0.0000 |
| var | h=6 | 1.175 | 1.175 | EXACT | 0.0000 |
| var | h=12 | 1.202 | 1.202 | EXACT | 0.0000 |
| factor | h=1 | 1.192 | 1.192 | EXACT | 0.0000 |
| factor | h=3 | 1.170 | 1.170 | EXACT | 0.0000 |
| factor | h=6 | 1.260 | 1.260 | EXACT | 0.0000 |
| factor | h=12 | 1.377 | 1.377 | EXACT | 0.0000 |
| chronos2_zs | h=1 | 0.984 | 0.984 | EXACT | 0.0000 |
| chronos2_zs | h=3 | 0.981 | 0.981 | EXACT | 0.0000 |
| chronos2_zs | h=6 | 0.997 | 0.997 | EXACT | 0.0000 |
| chronos2_zs | h=12 | 1.021 | 1.021 | EXACT | 0.0000 |
| chronos2_ft | h=1 | 1.011 | 1.011 | EXACT | 0.0000 |
| chronos2_ft | h=3 | 1.025 | 1.025 | EXACT | 0.0000 |
| chronos2_ft | h=6 | 1.085 | 1.085 | EXACT | 0.0000 |
| chronos2_ft | h=12 | 1.205 | 1.205 | EXACT | 0.0000 |

## 3. Subperiod RMSE (tab:subperiods)

| Subperiod | Method | Horizon | Paper | Result | Status | Diff |
|-----------|--------|---------|-------|--------|--------|------|
| pre_covid | random_walk | h=1 | 0.966 | 0.966 | EXACT | 0.0000 |
| pre_covid | random_walk | h=3 | 1.138 | 1.138 | EXACT | 0.0000 |
| pre_covid | random_walk | h=6 | 1.836 | 1.836 | EXACT | 0.0000 |
| pre_covid | random_walk | h=12 | 2.655 | 2.654 | OK (rounding) | 0.0010 |
| pre_covid | arima | h=1 | 0.897 | 0.897 | EXACT | 0.0000 |
| pre_covid | arima | h=3 | 1.118 | 1.118 | EXACT | 0.0000 |
| pre_covid | arima | h=6 | 1.836 | 1.836 | EXACT | 0.0000 |
| pre_covid | arima | h=12 | 2.618 | 2.618 | EXACT | 0.0000 |
| pre_covid | chronos2_zs | h=1 | 0.862 | 0.862 | EXACT | 0.0000 |
| pre_covid | chronos2_zs | h=3 | 1.033 | 1.033 | EXACT | 0.0000 |
| pre_covid | chronos2_zs | h=6 | 1.773 | 1.773 | EXACT | 0.0000 |
| pre_covid | chronos2_zs | h=12 | 2.633 | 2.633 | EXACT | 0.0000 |
| pre_covid | chronos2_ft | h=1 | 0.882 | 0.882 | EXACT | 0.0000 |
| pre_covid | chronos2_ft | h=3 | 1.081 | 1.081 | EXACT | 0.0000 |
| pre_covid | chronos2_ft | h=6 | 1.844 | 1.844 | EXACT | 0.0000 |
| pre_covid | chronos2_ft | h=12 | 2.739 | 2.739 | EXACT | 0.0000 |
| covid | random_walk | h=1 | 2.328 | 2.328 | EXACT | 0.0000 |
| covid | random_walk | h=3 | 2.921 | 2.921 | EXACT | 0.0000 |
| covid | random_walk | h=6 | 3.149 | 3.149 | EXACT | 0.0000 |
| covid | random_walk | h=12 | 3.411 | 3.411 | EXACT | 0.0000 |
| covid | arima | h=1 | 2.491 | 2.491 | EXACT | 0.0000 |
| covid | arima | h=3 | 3.045 | 3.045 | EXACT | 0.0000 |
| covid | arima | h=6 | 3.609 | 3.609 | EXACT | 0.0000 |
| covid | arima | h=12 | 4.130 | 4.130 | EXACT | 0.0000 |
| covid | chronos2_zs | h=1 | 2.519 | 2.519 | EXACT | 0.0000 |
| covid | chronos2_zs | h=3 | 3.008 | 3.008 | EXACT | 0.0000 |
| covid | chronos2_zs | h=6 | 3.495 | 3.495 | EXACT | 0.0000 |
| covid | chronos2_zs | h=12 | 4.003 | 4.003 | EXACT | 0.0000 |
| covid | chronos2_ft | h=1 | 2.466 | 2.466 | EXACT | 0.0000 |
| covid | chronos2_ft | h=3 | 3.086 | 3.086 | EXACT | 0.0000 |
| covid | chronos2_ft | h=6 | 3.605 | 3.605 | EXACT | 0.0000 |
| covid | chronos2_ft | h=12 | 4.234 | 4.234 | EXACT | 0.0000 |
| post_covid | random_walk | h=1 | 0.963 | 0.963 | EXACT | 0.0000 |
| post_covid | random_walk | h=3 | 1.207 | 1.207 | EXACT | 0.0000 |
| post_covid | random_walk | h=6 | 1.374 | 1.374 | EXACT | 0.0000 |
| post_covid | random_walk | h=12 | 1.694 | 1.693 | OK (rounding) | 0.0010 |
| post_covid | arima | h=1 | 0.900 | 0.900 | EXACT | 0.0000 |
| post_covid | arima | h=3 | 1.118 | 1.118 | EXACT | 0.0000 |
| post_covid | arima | h=6 | 1.326 | 1.326 | EXACT | 0.0000 |
| post_covid | arima | h=12 | 1.645 | 1.645 | EXACT | 0.0000 |
| post_covid | chronos2_zs | h=1 | 0.953 | 0.953 | EXACT | 0.0000 |
| post_covid | chronos2_zs | h=3 | 1.183 | 1.183 | EXACT | 0.0000 |
| post_covid | chronos2_zs | h=6 | 1.334 | 1.334 | EXACT | 0.0000 |
| post_covid | chronos2_zs | h=12 | 1.734 | 1.734 | EXACT | 0.0000 |
| post_covid | chronos2_ft | h=1 | 1.023 | 1.023 | EXACT | 0.0000 |
| post_covid | chronos2_ft | h=3 | 1.324 | 1.324 | EXACT | 0.0000 |
| post_covid | chronos2_ft | h=6 | 1.641 | 1.641 | EXACT | 0.0000 |
| post_covid | chronos2_ft | h=12 | 3.011 | 3.011 | EXACT | 0.0000 |

## 4. Per-Variable Test MASE (tab:per_variable_test)

| Variable | Method | Horizon | Paper | Result | Status | Diff |
|----------|--------|---------|-------|--------|--------|------|
| cpi | random_walk | h=1 | 1.000 | 1.000 | EXACT | 0.0000 |
| cpi | random_walk | h=3 | 1.000 | 1.000 | EXACT | 0.0000 |
| cpi | random_walk | h=6 | 1.000 | 1.000 | EXACT | 0.0000 |
| cpi | random_walk | h=12 | 1.000 | 1.000 | EXACT | 0.0000 |
| cpi | arima | h=1 | 1.019 | 1.019 | EXACT | 0.0000 |
| cpi | arima | h=3 | 1.015 | 1.015 | EXACT | 0.0000 |
| cpi | arima | h=6 | 0.996 | 0.996 | EXACT | 0.0000 |
| cpi | arima | h=12 | 0.998 | 0.998 | EXACT | 0.0000 |
| cpi | var | h=1 | 1.053 | 1.053 | EXACT | 0.0000 |
| cpi | var | h=3 | 1.212 | 1.212 | EXACT | 0.0000 |
| cpi | var | h=6 | 1.270 | 1.270 | EXACT | 0.0000 |
| cpi | var | h=12 | 1.084 | 1.084 | EXACT | 0.0000 |
| cpi | factor | h=1 | 1.372 | 1.372 | EXACT | 0.0000 |
| cpi | factor | h=3 | 1.320 | 1.320 | EXACT | 0.0000 |
| cpi | factor | h=6 | 1.286 | 1.286 | EXACT | 0.0000 |
| cpi | factor | h=12 | 1.108 | 1.108 | EXACT | 0.0000 |
| cpi | chronos2_zs | h=1 | 1.024 | 1.024 | EXACT | 0.0000 |
| cpi | chronos2_zs | h=3 | 1.016 | 1.016 | EXACT | 0.0000 |
| cpi | chronos2_zs | h=6 | 0.992 | 0.992 | EXACT | 0.0000 |
| cpi | chronos2_zs | h=12 | 0.956 | 0.956 | EXACT | 0.0000 |
| cpi | chronos2_ft | h=1 | 1.026 | 1.026 | EXACT | 0.0000 |
| cpi | chronos2_ft | h=3 | 1.055 | 1.055 | EXACT | 0.0000 |
| cpi | chronos2_ft | h=6 | 1.087 | 1.087 | EXACT | 0.0000 |
| cpi | chronos2_ft | h=12 | 1.062 | 1.062 | EXACT | 0.0000 |
| industrial_production | random_walk | h=1 | 1.000 | 1.000 | EXACT | 0.0000 |
| industrial_production | random_walk | h=3 | 1.000 | 1.000 | EXACT | 0.0000 |
| industrial_production | random_walk | h=6 | 1.000 | 1.000 | EXACT | 0.0000 |
| industrial_production | random_walk | h=12 | 1.000 | 1.000 | EXACT | 0.0000 |
| industrial_production | arima | h=1 | 1.043 | 1.043 | EXACT | 0.0000 |
| industrial_production | arima | h=3 | 1.007 | 1.007 | EXACT | 0.0000 |
| industrial_production | arima | h=6 | 1.067 | 1.067 | EXACT | 0.0000 |
| industrial_production | arima | h=12 | 1.057 | 1.056 | OK (rounding) | 0.0010 |
| industrial_production | var | h=1 | 0.978 | 0.978 | EXACT | 0.0000 |
| industrial_production | var | h=3 | 0.980 | 0.980 | EXACT | 0.0000 |
| industrial_production | var | h=6 | 1.025 | 1.025 | EXACT | 0.0000 |
| industrial_production | var | h=12 | 1.221 | 1.221 | EXACT | 0.0000 |
| industrial_production | factor | h=1 | 1.184 | 1.184 | EXACT | 0.0000 |
| industrial_production | factor | h=3 | 1.091 | 1.091 | EXACT | 0.0000 |
| industrial_production | factor | h=6 | 1.186 | 1.186 | EXACT | 0.0000 |
| industrial_production | factor | h=12 | 1.589 | 1.589 | EXACT | 0.0000 |
| industrial_production | chronos2_zs | h=1 | 1.024 | 1.023 | OK (rounding) | 0.0010 |
| industrial_production | chronos2_zs | h=3 | 0.981 | 0.981 | EXACT | 0.0000 |
| industrial_production | chronos2_zs | h=6 | 0.974 | 0.974 | EXACT | 0.0000 |
| industrial_production | chronos2_zs | h=12 | 1.048 | 1.047 | OK (rounding) | 0.0010 |
| industrial_production | chronos2_ft | h=1 | 1.115 | 1.115 | EXACT | 0.0000 |
| industrial_production | chronos2_ft | h=3 | 1.093 | 1.092 | OK (rounding) | 0.0010 |
| industrial_production | chronos2_ft | h=6 | 1.170 | 1.170 | EXACT | 0.0000 |
| industrial_production | chronos2_ft | h=12 | 1.435 | 1.435 | EXACT | 0.0000 |
| retail_sales | random_walk | h=1 | 1.000 | 1.000 | EXACT | 0.0000 |
| retail_sales | random_walk | h=3 | 1.000 | 1.000 | EXACT | 0.0000 |
| retail_sales | random_walk | h=6 | 1.000 | 1.000 | EXACT | 0.0000 |
| retail_sales | random_walk | h=12 | 1.000 | 1.000 | EXACT | 0.0000 |
| retail_sales | arima | h=1 | 0.971 | 0.971 | EXACT | 0.0000 |
| retail_sales | arima | h=3 | 1.003 | 1.003 | EXACT | 0.0000 |
| retail_sales | arima | h=6 | 1.069 | 1.069 | EXACT | 0.0000 |
| retail_sales | arima | h=12 | 1.069 | 1.068 | OK (rounding) | 0.0010 |
| retail_sales | var | h=1 | 1.001 | 1.001 | EXACT | 0.0000 |
| retail_sales | var | h=3 | 1.054 | 1.054 | EXACT | 0.0000 |
| retail_sales | var | h=6 | 1.212 | 1.212 | EXACT | 0.0000 |
| retail_sales | var | h=12 | 1.278 | 1.278 | EXACT | 0.0000 |
| retail_sales | factor | h=1 | 1.140 | 1.140 | EXACT | 0.0000 |
| retail_sales | factor | h=3 | 1.086 | 1.085 | OK (rounding) | 0.0010 |
| retail_sales | factor | h=6 | 1.167 | 1.167 | EXACT | 0.0000 |
| retail_sales | factor | h=12 | 1.323 | 1.323 | EXACT | 0.0000 |
| retail_sales | chronos2_zs | h=1 | 0.993 | 0.993 | EXACT | 0.0000 |
| retail_sales | chronos2_zs | h=3 | 0.977 | 0.977 | EXACT | 0.0000 |
| retail_sales | chronos2_zs | h=6 | 1.036 | 1.036 | EXACT | 0.0000 |
| retail_sales | chronos2_zs | h=12 | 1.102 | 1.102 | EXACT | 0.0000 |
| retail_sales | chronos2_ft | h=1 | 1.022 | 1.022 | EXACT | 0.0000 |
| retail_sales | chronos2_ft | h=3 | 1.027 | 1.027 | EXACT | 0.0000 |
| retail_sales | chronos2_ft | h=6 | 1.108 | 1.108 | EXACT | 0.0000 |
| retail_sales | chronos2_ft | h=12 | 1.320 | 1.320 | EXACT | 0.0000 |
| unemployment | random_walk | h=1 | 1.000 | 1.000 | EXACT | 0.0000 |
| unemployment | random_walk | h=3 | 1.000 | 1.000 | EXACT | 0.0000 |
| unemployment | random_walk | h=6 | 1.000 | 1.000 | EXACT | 0.0000 |
| unemployment | random_walk | h=12 | 1.000 | 1.000 | EXACT | 0.0000 |
| unemployment | arima | h=1 | 0.876 | 0.876 | EXACT | 0.0000 |
| unemployment | arima | h=3 | 0.941 | 0.941 | EXACT | 0.0000 |
| unemployment | arima | h=6 | 0.998 | 0.998 | EXACT | 0.0000 |
| unemployment | arima | h=12 | 0.994 | 0.994 | EXACT | 0.0000 |
| unemployment | var | h=1 | 0.884 | 0.884 | EXACT | 0.0000 |
| unemployment | var | h=3 | 1.052 | 1.052 | EXACT | 0.0000 |
| unemployment | var | h=6 | 1.194 | 1.194 | EXACT | 0.0000 |
| unemployment | var | h=12 | 1.224 | 1.224 | EXACT | 0.0000 |
| unemployment | factor | h=1 | 1.072 | 1.072 | EXACT | 0.0000 |
| unemployment | factor | h=3 | 1.182 | 1.182 | EXACT | 0.0000 |
| unemployment | factor | h=6 | 1.400 | 1.400 | EXACT | 0.0000 |
| unemployment | factor | h=12 | 1.487 | 1.487 | EXACT | 0.0000 |
| unemployment | chronos2_zs | h=1 | 0.896 | 0.896 | EXACT | 0.0000 |
| unemployment | chronos2_zs | h=3 | 0.950 | 0.950 | EXACT | 0.0000 |
| unemployment | chronos2_zs | h=6 | 0.988 | 0.988 | EXACT | 0.0000 |
| unemployment | chronos2_zs | h=12 | 0.978 | 0.978 | EXACT | 0.0000 |
| unemployment | chronos2_ft | h=1 | 0.880 | 0.880 | EXACT | 0.0000 |
| unemployment | chronos2_ft | h=3 | 0.924 | 0.924 | EXACT | 0.0000 |
| unemployment | chronos2_ft | h=6 | 0.977 | 0.977 | EXACT | 0.0000 |
| unemployment | chronos2_ft | h=12 | 1.003 | 1.003 | EXACT | 0.0000 |

## 5. Ablation (tab:ablation)

Ablation values are computed from `results/ablation_results.json`.

| Step | Era | Paper | Result | Status | Diff |
|------|-----|-------|--------|--------|------|
| Zero-shot baseline | validation | 0.999 | N/A | SKIPPED (no match in ablation data) | --- |
| Zero-shot baseline | test | 0.996 | N/A | SKIPPED (no match in ablation data) | --- |
| + context_length = 96 | validation | 0.968 | N/A | SKIPPED (no match in ablation data) | --- |
| + context_length = 96 | test | 1.001 | N/A | SKIPPED (no match in ablation data) | --- |
| + brent_crude | validation | 0.963 | N/A | SKIPPED (no match in ablation data) | --- |
| + brent_crude | test | 1.005 | N/A | SKIPPED (no match in ablation data) | --- |
| + policy_rate | validation | 0.951 | N/A | SKIPPED (no match in ablation data) | --- |
| + policy_rate | test | 1.046 | N/A | SKIPPED (no match in ablation data) | --- |
| + us_cpi | validation | 0.941 | N/A | SKIPPED (no match in ablation data) | --- |
| + us_cpi | test | 1.064 | N/A | SKIPPED (no match in ablation data) | --- |
| + nok_eur | validation | 0.944 | N/A | SKIPPED (no match in ablation data) | --- |
| + nok_eur | test | 1.080 | N/A | SKIPPED (no match in ablation data) | --- |
| + LoRA fine-tune | validation | 0.943 | N/A | SKIPPED (no match in ablation data) | --- |
| + LoRA fine-tune | test | 1.081 | N/A | SKIPPED (no match in ablation data) | --- |

## Summary

- **Total checks:** 192
- **Exact matches:** 179
- **Rounding matches (diff <= 0.0015):** 10
- **Mismatches:** 3

### All Mismatches

- Validation ets h=1: paper=0.964, result=0.953
- Validation ets h=3: paper=1.002, result=1.011
- Validation ets h=12: paper=1.043, result=1.054
