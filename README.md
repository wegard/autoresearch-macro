# Automated Feature Engineering for Macro Forecasting

**Collaborators:** Vegard Larsen, Leif Anders Thorsrud
**Started:** 2026-03-27
**Status:** First search experiment complete (6.6% improvement)

## What

Agentic outer-loop search over data transformations, covariate selection, and fine-tuning settings for time series foundation models (Chronos-2). Applied to pseudo-real-time forecasting of the Norwegian macroeconomy.

## Research question

Can an agentic search procedure improve macro forecasts by selecting data representations, covariates, and fine-tuning settings — relative to zero-shot foundation models, manually tuned models, and standard baselines?

## Repository structure

```
autoresearch-macro/
├── README.md                   # this file
├── METHODOLOGY.md              # formal study design (source of truth for the paper)
├── EXPERIMENT-1.md             # first experiment guide
├── CONTEXT.md                  # session resume for AI assistants
├── DESIGN.md                   # original research design brainstorm
├── ROADMAP.md                  # phased timeline and deliverables
├── STATUS.md                   # current status and results
├── CLAUDE.md                   # instructions for Claude Code
├── log.md                      # decision log
├── program.md                  # agent instructions for search loop
├── src/
│   ├── prepare.py              # data pipeline — 18 variables, pseudo-real-time (LOCKED)
│   ├── train.py                # Chronos-2 + AutoGluon scaffold (AGENT-EDITABLE)
│   ├── evaluate.py             # evaluation harness, metrics, comparison (LOCKED)
│   ├── baselines.py            # 5 classical baselines (RW, SN, AR, ARIMA, ETS)
│   └── search.py               # LLM-guided outer loop controller
├── tests/                      # 90 tests (pytest)
├── configs/
│   ├── publication_lags.yml    # days-after-month-end for each variable
│   └── search_space.yml        # valid parameter ranges for the search
├── data/                       # cached data (gitignored)
├── results/                    # experiment logs, metrics (gitignored)
│   └── validation/             # 6 methods evaluated on 2006-2015
├── webapp/                     # Interactive Quarto + D3.js dashboard
│   ├── _quarto.yml             # Quarto website config
│   ├── index.qmd               # Landing page
│   ├── data-pipeline.qmd       # Data sources and pseudo-real-time explorer
│   ├── baselines.qmd           # Classical baseline comparison
│   ├── foundation-model.qmd    # Chronos-2 results and model ladder
│   ├── search.qmd              # Search loop trajectory and analysis
│   ├── forecasts.qmd           # Rolling forecasts vs actuals (interactive)
│   ├── results.qmd             # Full comparison heatmap and tables
│   └── _data/                  # prepare_results.py, generate_forecasts.py + JSON
├── paper/                      # LaTeX paper
└── reference/
    └── autoresearch/           # Karpathy's repo, cloned for study
```

## Quick start

```bash
# Install all dependencies
uv sync --all-extras

# Download data and build panel
uv run python src/prepare.py

# Run all baselines on validation era
uv run python src/baselines.py --all --era validation --save

# Run zero-shot Chronos-2
uv run python src/train.py --era validation --save

# Compare results
uv run python src/evaluate.py --compare results/validation/random_walk results/validation/arima results/validation/chronos2_zs

# Run the LLM-guided search loop (requires ANTHROPIC_API_KEY in .env)
uv run python src/search.py --max-iterations 10

# Run tests
uv run pytest
```

## Web dashboard

An interactive Quarto + Observable Plot dashboard for exploring results.

```bash
# Prepare metrics data (converts results to JSON for the charts)
uv run python webapp/_data/prepare_results.py

# Generate rolling forecasts (requires GPU, ~5 min)
uv run python webapp/_data/generate_forecasts.py

# Live preview (opens browser with hot reload)
cd webapp && quarto preview

# Build static site (output in webapp/_site/)
cd webapp && quarto render
```

Requires [Quarto](https://quarto.org/docs/get-started/) (v1.4+). No npm/node setup needed — D3.js and Observable Plot are loaded via Quarto's built-in OJS engine.

## Environment variables

Set in `.env`:

```
FRED_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

- FRED API key: free at <https://fred.stlouisfed.org/docs/api/api_key.html>
- Anthropic API key: for the search loop's LLM-guided config proposals
- SSB and Norges Bank APIs are public (no key needed)

## Key design decisions

- **Agent constrained:** Search loop edits covariate selection, transforms, fine-tuning params — not model architecture
- **Rolling validation:** Expanding window, 2006-2015 validation era, 120 monthly origins
- **Pseudo-real-time:** Publication lags enforced at every forecast origin
- **LLM-guided search:** Claude proposes config changes based on past results and domain knowledge
- **Three-way ablation:** Decompose gains into (1) foundation model, (2) fine-tuning, (3) agentic search

## Current results (validation era 2006-2015, avg RMSE across targets)

| Method | h=1 | h=3 | h=6 | h=12 |
|--------|-----|-----|-----|------|
| Random walk | 1.202 | 1.533 | 1.958 | 2.683 |
| **ARIMA** | **1.164** | **1.504** | **1.910** | **2.641** |
| Chronos-2 (120M) zero-shot | 1.171 | 1.542 | 1.989 | 2.820 |

**Search experiment (30 iterations):** The LLM-guided search improved Chronos-2 by **6.6%** (MASE 1.94 → 1.82) by discovering that oil prices, the policy rate, and US inflation are the optimal covariates with a 96-month context window. Model: `amazon/chronos-2` (120M params).

## Links

- Karpathy autoresearch: https://github.com/karpathy/autoresearch
- Chronos-2: https://github.com/amazon-science/chronos-forecasting
- AutoGluon TimeSeries: https://auto.gluon.ai/stable/tutorials/timeseries/
