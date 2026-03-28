# Initial Prompt for Claude Code

> Copy everything below the line into Claude Code when starting in this repo.

---

Read the following files in order to understand the project:

1. README.md — project overview and repo structure
2. CLAUDE.md — your coding instructions and constraints
3. DESIGN.md — full research design
4. ROADMAP.md — project phases and timeline
5. PREPARE-SPEC.md — detailed specification for the data pipeline
6. log.md — decisions made so far
7. reference/autoresearch/prepare.py — Karpathy's data pipeline (our inspiration)
8. reference/autoresearch/program.md — Karpathy's agent instructions (our inspiration)

After reading, your first task is to implement `src/prepare.py` according to PREPARE-SPEC.md. This is the locked data pipeline that the search agent cannot modify. It must:

1. Download Norwegian macro series from the SSB API and Norges Bank API
2. Download global series from the FRED API
3. Handle frequency alignment (daily → monthly, quarterly → monthly)
4. Implement the `MacroPanel` dataclass with the `available_at(forecast_origin)` method that enforces pseudo-real-time data discipline (no future information leakage)
5. Implement transformation utilities (log_diff, pct_change, standardize, ma)
6. Implement the evaluation protocol: `build_validation_origins()`, `build_test_origins()`, `evaluate_forecasts()`
7. Implement evaluation metrics: RMSE, MAE, MASE, pinball loss
8. Provide a CLI interface for downloading, processing, and verifying data
9. Make publication lags configurable via `configs/publication_lags.yml`
10. Write tests in `tests/test_prepare.py`

Start by setting up the Python project structure (pyproject.toml, configs directory, test scaffolding), then implement prepare.py incrementally. Verify SSB table IDs are current — if any have changed, document the correct ones and proceed. Use placeholder logic for any series you can't verify access to, with clear TODO markers.

Environment variables needed: FRED_API_KEY (for FRED data) is stored in .env in the repo root. SSB and Norges Bank APIs are public and don't require keys.
