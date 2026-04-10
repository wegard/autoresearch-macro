# CLAUDE.md — Instructions for Claude Code

## Project

Automated feature engineering for macroeconomic forecasting using agentic search over time series foundation models.

## Repository layout

- `src/prepare.py` — Norway data pipeline (SSB + Norges Bank + FRED). **Locked from the search agent.**
- `src/prepare_canada.py` — Canada data pipeline (Statistics Canada + Bank of Canada + FRED). **Locked.**
- `src/prepare_sweden.py` — Sweden data pipeline (SCB + Riksbank + FRED). **Locked.**
- `src/train.py` — agent sandbox: loads **amazon/chronos-2 (120M params)** via AutoGluon `"Chronos-2"` key, applies covariate selection and LoRA fine-tuning config. **The search agent proposes changes to the config section at the top.**
- `src/evaluate.py` — frozen evaluation harness: metrics, results storage, comparison tables. **Locked.**
- `src/baselines.py` — classical + ML baselines: random walk, seasonal naive, AR, ARIMA, ETS, VAR, factor model, BVAR (Minnesota shrinkage), Elastic Net.
- `src/search.py` — outer loop controller: supports `--country {norway,canada,sweden}`, `--mode {llm,random,greedy}`, `--program <prompt.md>`, `--tag <label>`, multi-seed.
- `src/build_forecast_errors.py` — consolidates per-method results into a single `forecast_errors.parquet`.
- `src/tables/generate_tables.py` — script-generates LaTeX table fragments from the unified errors store.
- `configs/publication_lags.yml` — publication lag config (all three countries).
- `configs/search_space.yml` — valid parameter ranges for the search agent.
- `configs/manual_economist_benchmarks.yaml` — locked manual-benchmark configs per country (never revised after seeing results).
- `metadata/variable_catalog.csv`, `canada_target_decision.md`, `partner_activity_mapping.csv` — authoritative metadata.
- `prompts/blind.md`, `prompts/informed_{norway,canada,sweden}.md` — system prompts for the LLM search.
- `program.md` — legacy Norway-only agent instructions (kept for backward compat with existing Norway runs).
- `paper/REVISION-PLAN-4.md` — current execution spec for the three-country IJF revision.
- `data/` — cached data (gitignored).
- `results/` — experiment logs and saved metrics (gitignored).
- `reference/autoresearch/` — Karpathy's autoresearch repo, for study only.

## Coding conventions

- Python 3.11+
- Type hints on all functions
- Docstrings on public functions
- Use SSB API (JSON-stat2) for Norwegian data, `fredapi` for global data, Norges Bank SDMX API for exchange rates and policy rate
- Use `chronos-forecasting` and `autogluon.timeseries` as the model interface (model: amazon/chronos-2, 120M params)
- Logging via standard `logging` module
- Reproducibility: seed all random state, log all experiment configs

## Testing

- `uv run pytest` for all tests (126 tests across 11 test files as of 2026-04-10)
- `uv run ruff check src/ tests/` for linting
- Tests must pass after every change
- Installing deps: use `uv sync --extra ml --extra dev` to get both AutoGluon and pytest. Syncing only one extra will uninstall the other.

## Methodology document

`METHODOLOGY.md` is the **source of truth** for the paper. When making changes to the data pipeline, evaluation protocol, baselines, model configuration, search procedure, or any other methodological aspect, **update METHODOLOGY.md to reflect those changes**. Also update the changelog at the bottom of the file.

## Key constraints

- The search loop must respect pseudo-real-time data discipline (no future data at any forecast origin)
- Rolling expanding-window validation, not a single train/test split
- Validation era: 2006-01 to 2015-12. Test era: 2016-01 onward (frozen, no tuning). Three-country common end date: 2025-03.
- Search agent is constrained to data pipeline and fine-tuning — never touches model architecture
- All experiments must be logged with full config for reproducibility
- When launching an LLM search, set `HF_HUB_OFFLINE=1` — it skips AutoGluon's HuggingFace HEAD check and cuts model-loading time significantly.
