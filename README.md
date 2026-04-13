# Automated Feature Engineering for Macro Forecasting

**Collaborators:** Vegard Larsen, Leif Anders Thorsrud
**Started:** 2026-03-27
**Target journal:** International Journal of Forecasting
**Status:** Three-country expansion (Norway + Canada + Sweden) in progress per `paper/REVISION-PLAN-4.md`. Search runs complete for Norway; Canada and Sweden informed/random/greedy runs complete, blind runs pending. See `STATUS.md`.

## What

Agentic outer-loop search over data transformations, covariate selection, and fine-tuning settings for time series foundation models (Chronos-2). Applied to pseudo-real-time forecasting of Norway, Canada, and Sweden.

## Research question

Can an agentic search procedure improve macro forecasts across small open economies by selecting data representations, covariates, and fine-tuning settings — and do validation-era gains survive out-of-sample regime changes (COVID, post-2022 inflation)?

## Repository structure

```
autoresearch-macro/
├── README.md                   # this file
├── METHODOLOGY.md              # formal study design — source of truth for the paper (keep updated!)
├── STATUS.md                   # current status and per-country search matrix
├── CLAUDE.md                   # instructions for Claude Code
├── log.md                      # decision log
├── ROADMAP.md                  # phased timeline and deliverables
├── CONTEXT.md                  # session resume for AI assistants
├── DESIGN.md                   # original research design brainstorm (historical)
├── EXPERIMENT-1.md             # first experiment guide (historical)
├── PREPARE-SPEC.md             # prepare.py spec (historical)
├── program.md                  # legacy Norway agent instructions
├── prompts/                    # LLM search prompts
│   ├── blind.md                # domain-blind agent
│   ├── informed_norway.md      # domain-informed, Norway
│   ├── informed_canada.md      # domain-informed, Canada
│   └── informed_sweden.md      # domain-informed, Sweden
├── src/
│   ├── prepare.py              # Norway data pipeline (LOCKED)
│   ├── prepare_canada.py       # Canada data pipeline (LOCKED)
│   ├── prepare_sweden.py       # Sweden data pipeline (LOCKED)
│   ├── train.py                # Chronos-2 + AutoGluon scaffold (AGENT-EDITABLE)
│   ├── evaluate.py             # evaluation harness, metrics, comparison (LOCKED)
│   ├── baselines.py            # Classical + ML baselines: RW, SN, AR, ARIMA, ETS, VAR, factor, BVAR, Elastic Net
│   ├── search.py               # LLM/random/greedy outer-loop controller (multi-country, multi-seed)
│   ├── build_forecast_errors.py # consolidates results into forecast_errors.parquet
│   └── tables/generate_tables.py # script-generates LaTeX tables from results
├── tests/                      # 126 tests (pytest)
├── configs/
│   ├── publication_lags.yml    # per-country publication lags
│   ├── search_space.yml        # valid parameter ranges for the search
│   └── manual_economist_benchmarks.yaml # locked per-country manual benchmarks
├── metadata/
│   ├── variable_catalog.csv
│   ├── canada_target_decision.md
│   └── partner_activity_mapping.csv
├── data/                       # cached data (gitignored)
├── results/                    # experiment logs, metrics (gitignored)
│   ├── {norway,canada,sweden}/ # per-country search states and logs
│   ├── validation/             # per-method validation-era results
│   └── test/                   # per-method test-era results
├── audit/                      # audit trail against the original Norway paper
├── paper/
│   ├── main.tex                # LaTeX manuscript
│   └── REVISION-PLAN-{1..4}.md # revision execution specs
├── webapp/                     # Interactive Quarto + D3.js dashboard
└── reference/
    └── autoresearch/           # Karpathy's repo, cloned for study
```

## Quick start

```bash
# Install all dependencies (AutoGluon + dev tools)
uv sync --extra ml --extra dev

# Download data and build panels for all three countries
uv run python src/prepare.py
uv run python src/prepare_canada.py
uv run python src/prepare_sweden.py

# Run all baselines on validation era
uv run python src/baselines.py --all --era validation --save --country norway

# Run zero-shot Chronos-2
uv run python src/train.py --era validation --save --country norway

# Run the LLM-guided search loop (requires ANTHROPIC_API_KEY in .env)
# HF_HUB_OFFLINE=1 skips HuggingFace HEAD checks during model load
HF_HUB_OFFLINE=1 uv run python src/search.py \
    --country norway --mode llm --seed 42 \
    --program prompts/informed_norway.md --max-iterations 50

# Blind search — use --tag to get a separate state file
HF_HUB_OFFLINE=1 uv run python src/search.py \
    --country norway --mode llm --seed 42 \
    --program prompts/blind.md --tag blind --max-iterations 50

# Consolidate errors and regenerate tables
uv run python src/build_forecast_errors.py
uv run python src/tables/generate_tables.py

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

## Publishing to MacroLab

This repo can publish its rendered web dashboard into MacroLab as a versioned static artifact. The integration contract is:

- rendered static site from `webapp/_site/`
- small manifest file `macrolab-manifest.json`

See [`MACROLAB-INTEGRATION.md`](MACROLAB-INTEGRATION.md) for the architecture and expected VPS layout.

### Build a manifest only

```bash
./.venv/bin/python scripts/build_macrolab_manifest.py \
  --output /tmp/macrolab-manifest.json
```

This computes a MacroLab-facing manifest from the current results and includes:

- published app entrypoint
- source git revision
- summary stats derived from the current outputs

### Publish a static release

```bash
bash scripts/publish_to_macrolab.sh \
  --artifact-root /opt/macrolab/project-artifacts \
  --macrolab-root /opt/macrolab
```

What this does:

1. regenerates the webapp data JSON
2. renders the Quarto site
3. copies the rendered site into a versioned release directory
4. writes `macrolab-manifest.json` into that release
5. updates the public symlink for MacroLab to serve
6. calls MacroLab's sync script if it exists

Useful flags:

- `--skip-build` to reuse an existing `webapp/_site/`
- `--skip-sync` to stage artifacts without touching MacroLab metadata
- `--repo-url` and `--paper-url` to add links in the MacroLab shell

### Deploy on VPS

On the VPS where MacroLab is running, clone this repo and publish:

```bash
# One-time: clone the repo
cd /opt
git clone https://github.com/wegard/autoresearch-macro.git
cd autoresearch-macro

# Install Quarto if not present (one-time)
# See https://quarto.org/docs/get-started/

# Build site from committed data + publish to MacroLab
bash scripts/publish_to_macrolab.sh \
  --render-only \
  --macrolab-root /opt/macrolab \
  --repo-url https://github.com/wegard/autoresearch-macro
```

To update after new results are pushed:

```bash
cd /opt/autoresearch-macro
git pull
bash scripts/publish_to_macrolab.sh \
  --render-only \
  --macrolab-root /opt/macrolab
```

The `--render-only` flag skips data regeneration (which requires raw `results/`) and only runs `quarto render` using the committed JSON data files.

### Dry-run locally

```bash
bash scripts/publish_to_macrolab.sh \
  --artifact-root /tmp/macrolab-artifacts \
  --macrolab-root /home/vegard/MacroLab \
  --skip-build \
  --skip-sync
```

This is useful for validating the release layout before wiring the project into production MacroLab.

## Environment variables

Set in `.env`:

```
FRED_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

- FRED API key: free at <https://fred.stlouisfed.org/docs/api/api_key.html>
- Anthropic API key: for the search loop's LLM-guided config proposals
- SSB and Norges Bank APIs are public (no key needed)

## Methodology

The formal study design is documented in [`METHODOLOGY.md`](METHODOLOGY.md). This is the **source of truth** for the paper — it covers the research question, hypotheses, data specification, evaluation protocol, metrics, baselines, foundation model details, search procedure, and reproducibility notes. Keep it updated when methods change.

## Key design decisions

- **Agent constrained:** Search loop edits covariate selection, transforms, fine-tuning params — not model architecture
- **Rolling validation:** Expanding window, 2006-2015 validation era, 120 monthly origins per country
- **Pseudo-real-time:** Publication lags enforced at every forecast origin, for all three countries
- **Search comparators:** Informed LLM, blind (domain-stripped) LLM, random, greedy stepwise, manual economist benchmark
- **Three countries, harmonized design:** Norway, Canada, Sweden — same targets, same horizons, same covariate template, common evaluation window 2006-01 to 2025-03

## Current results snapshot (validation era, avg MASE)

| Country | Zero-shot | Informed LLM (seed 42) | Blind LLM (seed 42) | Random | Greedy |
|---------|-----------|------------------------|---------------------|--------|--------|
| Norway  | 0.999 | 0.975 | 0.980 | 0.942 | 0.922 |
| Canada  | —     | 0.843 | pending | 0.847 | 0.841 |
| Sweden  | —     | 1.006 | pending | 0.936 | 0.992 |

**Key finding (Norway):** Agent-tuned configs improve validation MASE by 2-8% but frequently fail to generalize to the test era (COVID + post-2022 inflation). Zero-shot Chronos-2 is often more robust across regime changes than tuned pipelines or classical baselines. See `STATUS.md` for full per-country numbers.

Model: `amazon/chronos-2` (120M parameters) via AutoGluon 1.5.0.

## Links

- Karpathy autoresearch: https://github.com/karpathy/autoresearch
- Chronos-2: https://github.com/amazon-science/chronos-forecasting
- AutoGluon TimeSeries: https://auto.gluon.ai/stable/tutorials/timeseries/
