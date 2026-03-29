# Experiment 1: LLM-Guided Search over Forecasting Pipeline

## Goal

Test whether an LLM-guided search loop can discover a Chronos-2 configuration that beats classical baselines (ARIMA) on Norwegian macroeconomic forecasting.

## Background

We have established that:
- **ARIMA** is the best classical baseline (avg RMSE 2.641 at h=12 on validation era 2006-2015)
- **Chronos-2 (120M) zero-shot** (univariate, no covariates, no fine-tuning) is competitive at h=1 (1.171 vs ARIMA 1.164) but falls behind at longer horizons (avg RMSE 2.820 at h=12)

The model is **amazon/chronos-2** (120M parameters) with **native covariate support** and **LoRA fine-tuning**. Unlike the earlier Chronos-Bolt experiments, covariates and fine-tuning are now architecturally effective.

The search loop will let Claude propose config changes — which covariates to include, how to transform the data, context length, and fine-tuning settings — and evaluate whether each change improves forecasts.

## What the search controls

The search agent can modify these parameters in `train.py`:

| Parameter | Default | Search range |
|-----------|---------|-------------|
| **covariates** | `[]` (none) | Any subset of 14 available variables |
| **transforms** | `{}` (none) | log_diff, pct_change, standardize, moving avg (covariates only) |
| **context_length** | `null` (all, up to 8192) | 24, 36, 48, 64, 96, 128, or null |
| **fine_tune** | `false` | true/false (LoRA fine-tuning) |
| **fine_tune_steps** | 1000 | 100, 500, 1000, 2000 |
| **fine_tune_lr** | 1e-5 | 1e-6 to 1e-4 |
| **grouping** | `univariate` | univariate, all_targets |
| **num_samples** | 20 | 10, 20, 50 |

Model: **amazon/chronos-2** (120M params) — native past/known covariate support, LoRA fine-tuning.

Available covariates: house_prices, credit, exports, imports, nok_eur, nok_usd, policy_rate, brent_crude, sp500, fed_funds, us_cpi, vix, global_epu, euro_area_gdp.

## Prerequisites

### 1. Data must be downloaded

If you haven't already:
```bash
uv run python src/prepare.py
```

Verify with:
```bash
uv run python src/prepare.py --info
```

You should see 18 variables, ~951 months.

### 2. Dependencies must be installed

```bash
uv sync --all-extras
```

This installs core deps, dev tools (pytest, ruff), and ML deps (chronos-forecasting, autogluon, torch).

### 3. API keys must be set

Add to `.env` in the project root:
```
FRED_API_KEY=your_fred_key
ANTHROPIC_API_KEY=your_anthropic_key
```

The search loop calls Claude Sonnet via the Anthropic API to propose config changes. Each iteration makes one API call (~500 tokens in, ~200 tokens out).

### 4. GPU should be available

Verify:
```bash
uv run python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"none\"}')"
```

Chronos-2 runs on CPU too, but GPU is ~10x faster. Each iteration takes ~30s on GPU (quick eval, 20 origins) or ~3 min (full eval, 120 origins).

### 5. Tests should pass

```bash
uv run pytest
```

All 90 tests should pass.

## Running the experiment

### Quick smoke test (3 iterations)

```bash
uv run python src/search.py --max-iterations 3
```

This will:
1. Establish a baseline score (zero-shot, no covariates)
2. Call Claude 3 times to propose config changes
3. Evaluate each proposal on 20 subsampled origins
4. If improved, run full 120-origin evaluation to confirm
5. Accept or reject based on full evaluation

Expected runtime: ~5-10 minutes (depending on whether proposals trigger full evals).

### Full overnight run

```bash
uv run python src/search.py --max-iterations 50
```

Or run indefinitely until you interrupt with Ctrl+C:
```bash
uv run python src/search.py
```

The state is saved after every iteration. You can always resume:
```bash
uv run python src/search.py --resume
```

### Monitoring progress

In another terminal:
```bash
# Check current status
uv run python src/search.py --status

# Watch the log
tail -f results/search_log.jsonl | python -m json.tool

# Quick look at iteration scores
cat results/search_log.jsonl | python -c "
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    score = r.get('full_score') or r.get('quick_score') or 'N/A'
    print(f\"Iter {r['iteration']:3d}  {r['status']:10s}  score={score}  {r['description']}\")
"
```

## What to look for

### During the run

1. **Does the score improve?** The baseline (zero-shot, univariate) should have avg_mase ~1.7. Any accepted iteration means the agent found something better.
2. **What does the agent try first?** Typically: adding covariates (oil, exchange rates), then transformations, then context length changes.
3. **Are there errors?** Check for "error" status iterations. Common issues: fine-tuning OOM, incompatible transform on a variable.

### After the run

1. **Check the best config found:**
   ```bash
   uv run python src/search.py --status
   ```

2. **Run the best config on all 120 origins with full output:**
   ```bash
   uv run python src/train.py --config-file configs/current_config.json --era validation --save
   ```

3. **Compare against baselines:**
   ```bash
   uv run python src/evaluate.py --compare \
     results/validation/random_walk \
     results/validation/arima \
     results/validation/chronos2_zs \
     --metric mase
   ```
   (The search result will be saved under `results/validation/chronos2_zs` or similar.)

4. **Analyze the search trajectory:**
   ```bash
   cat results/search_log.jsonl | python -c "
   import json, sys
   accepted = []
   for line in sys.stdin:
       r = json.loads(line)
       if r['status'] == 'accepted':
           accepted.append(r)
   print(f'Accepted {len(accepted)} out of total iterations')
   for a in accepted:
       print(f\"  Iter {a['iteration']}: score={a.get('full_score', a.get('quick_score'))}  {a['description']}\")
   "
   ```

## Expected outcomes

### Optimistic
The agent discovers that adding brent_crude + nok_eur as covariates, with log_diff transforms on CPI and exports, brings avg MASE below 1.5 (beating ARIMA's ~1.57). Fine-tuning for 100 steps further improves to ~1.3.

### Realistic
The agent finds modest improvements from covariates (MASE ~1.55-1.65) but struggles to consistently beat ARIMA. Fine-tuning helps for some variables but not others. The best config uses 2-4 covariates with simple transforms.

### Pessimistic (still publishable)
The agent finds no configuration that consistently beats ARIMA. This is a valid negative result: zero-shot and lightly fine-tuned foundation models do not yet outperform classical methods on small-economy macro data under proper real-time evaluation discipline.

## After the experiment

### If the search finds improvements:
1. Run the best config on the **test era** (2016+):
   ```bash
   uv run python src/train.py --config-file configs/current_config.json --era test --save
   ```
2. Run baselines on the test era for comparison:
   ```bash
   uv run python src/baselines.py --all --era test --save
   ```
3. Proceed to Phase 4 (ablation) — decompose where gains come from.

### If the search does not find improvements:
1. Try **manual covariate selection** based on economic theory (Phase 2):
   - Create a config with theory-driven covariates (e.g., oil for CPI, credit for house prices)
   - Test fine-tuning with these manually chosen covariates
2. Try a **different model** (e.g., TimesFM, Lag-Llama) to test model-agnostic search
3. Try **more search iterations** (the agent may need 50+ iterations to explore the space)

### For the paper:
1. Save the full `results/search_log.jsonl` — this IS the experiment data
2. Save `results/search_state.json` — the final state
3. The search trajectory (what the agent tried, what worked, what didn't) is a key part of the analysis
