# Sweden — target variable notes

**Last updated:** 2026-04-11

## Active targets (3)

| Target | SCB table | First obs | Notes |
|--------|-----------|-----------|-------|
| `cpi` | `PR/PR0101/PR0101A/KPItotM` | 1980-01 | Annual change, % |
| `industrial_production` | `NV/NV0402/NV0402A/IPI2010KedjM` | 2000-01 | Calendar + seasonally adjusted, B+C (mining + manufacturing) |
| `unemployment` | `AM/AM0401/AM0401A/AKURLBefM` | 2001-01 | LFS, ages 15-74, seasonally adjusted, both sexes |

## Dropped target (1)

### `retail_sales`

**SCB table:** `HA/HA0101/HA0101B/Detoms07N` — Retail sales volume index, SA, NACE 47

**Reason for drop:** This SCB table only publishes data from **2023-01** onward (39 monthly observations as of 2026-04). The validation era is **2006-2015**, so there is zero overlap and `retail_sales` cannot be forecasted in any validation-era origin.

The column was previously included in the Sweden panel as a target. The training pipeline silently produced no forecasts for it, and per-target average MASE scores were computed across only the 3 surviving targets — masking the issue. This was discovered on 2026-04-11 while investigating why Sweden's blind LLM search converged to a no-improvement baseline.

**Implementation:** `prepare_sweden.DROPPED_VARIABLES = ["retail_sales"]`. The variable is filtered out at both build time (`build_panel_sweden`) and load time (`load_panel_sweden`) so cached panels with the column also get cleaned up.

**Impact on cross-country comparison:**
- Norway and Canada evaluate over 4 targets each (cpi, industrial_production, retail_sales, unemployment).
- Sweden evaluates over **3 targets** (cpi, industrial_production, unemployment).
- Cross-country MASE averages are not directly comparable. Tables in the paper should report Sweden alongside the 3-target Norway and Canada averages for an apples-to-apples comparison, in addition to (or instead of) the 4-target averages.
- All Sweden search results stored in `results/sweden/` from runs prior to 2026-04-11 already have this property — they evaluated over 3 targets, just without it being explicit.

**Revisit conditions:** If SCB publishes (or we discover) a longer-history retail sales table — for example a chained backward-extension to 2000 or earlier — restore the column by:
1. Removing `retail_sales` from `DROPPED_VARIABLES` in `src/prepare_sweden.py`
2. Updating the SCB path in `SCB_SERIES_CONFIG` if needed
3. Forcing a re-download: `uv run python src/prepare_sweden.py --force`
4. Rerunning all Sweden search experiments (the existing results are based on 3 targets and would be incomparable to a 4-target panel)
5. Updating `metadata/variable_catalog.csv` to change the role from `dropped` back to `target`
6. Removing the `"sweden": {"retail_sales"}` entry from `DROPPED_TARGETS` in `tests/test_country_metadata.py`
