# CLAUDE.md — Instructions for Claude Code

## Project

Automated feature engineering for macroeconomic forecasting using agentic search over time series foundation models.

## Repository layout

- `src/prepare.py` — data pipeline: downloads SSB and global macro data, handles publication lags, outputs standardized panel. **Locked from the search agent.**
- `src/train.py` — agent sandbox: loads **amazon/chronos-2 (120M params)** via AutoGluon `"Chronos-2"` key, applies covariate selection and LoRA fine-tuning config. **The search agent proposes changes to the config section at the top.**
- `src/evaluate.py` — frozen evaluation harness: metrics, results storage, comparison tables. **Locked from search agent.**
- `src/baselines.py` — classical baselines: random walk, seasonal naive, AR, ARIMA, ETS.
- `src/search.py` — outer loop controller: calls Claude API for config proposals, runs train.py, evaluates, accepts/rejects.
- `configs/publication_lags.yml` — publication lag config for pseudo-real-time discipline.
- `configs/search_space.yml` — valid parameter ranges for the search agent.
- `program.md` — natural language instructions and domain knowledge for the search agent.
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

- `uv run pytest` for all tests (90 tests across 5 test files)
- `uv run ruff check src/ tests/` for linting
- Tests must pass after every change

## Key constraints

- The search loop must respect pseudo-real-time data discipline (no future data at any forecast origin)
- Rolling expanding-window validation, not a single train/test split
- Validation era: 2006-01 to 2015-12. Test era: 2016-01 onward (frozen, no tuning)
- Search agent is constrained to data pipeline and fine-tuning — never touches model architecture
- All experiments must be logged with full config for reproducibility
