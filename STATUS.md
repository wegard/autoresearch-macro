# STATUS.md — Autoresearch Macro

**Stage:** Phase 1 complete, Phase 2-3 infrastructure ready
**Target:** TBD
**Collaborators:** Leif Anders Thorsrud
**Last updated:** 2026-03-28

## Submission history

Not yet written.

## What's built

### Data pipeline (Phase 0) — done
- `src/prepare.py` (1237 lines) — SSB, FRED, Norges Bank downloads with pseudo-real-time discipline
- 18 variables, 951 months (1947-01 to 2026-03)
- SSB table IDs and Norges Bank SDMX keys verified against live API (2026-03-28)
- Publication lags configured in `configs/publication_lags.yml`
- `MacroPanel.available_at()` enforces no-future-data discipline
- 36 tests in `tests/test_prepare.py`

### Evaluation harness — done
- `src/evaluate.py` (451 lines) — `ForecastResult`, `EvaluationResult`, save/load, comparison tables
- Subperiod reporting for test era (pre-COVID, COVID, post-COVID)
- 11 tests in `tests/test_evaluate.py`

### Baselines (Phase 1) — done
- `src/baselines.py` (547 lines) — 5 methods: random walk, seasonal naive, AR(p), ARIMA, ETS
- All evaluated on validation era (2006-2015, 120 monthly origins)
- Results saved in `results/validation/`
- 15 tests in `tests/test_baselines.py`

### Chronos-2 scaffold — done
- `src/train.py` (478 lines) — AutoGluon TimeSeriesPredictor + Chronos-2 interface
- Config section at top (agent-editable), `--config-file` override for search.py
- Zero-shot evaluated on validation era (results saved)
- 12 tests in `tests/test_train.py`

### Search loop (Phase 3 infrastructure) — done
- `src/search.py` (557 lines) — LLM-guided outer loop with Claude API
- `configs/search_space.yml` — parameter ranges
- `program.md` — full agent instructions with domain knowledge
- Two-phase evaluation: quick (20 origins) → full (120 origins)
- Persistent state, JSONL logging, resume support
- 16 tests in `tests/test_search.py`

### Totals
- **4,707 lines** of Python (source + tests)
- **90 tests**, all passing
- **6 methods** evaluated on validation era

## Validation era results (2006-2015, average RMSE across targets)

| Method | h=1 | h=3 | h=6 | h=12 |
|--------|-----|-----|-----|------|
| Random walk | 1.202 | 1.533 | 1.958 | 2.683 |
| Seasonal naive | 2.645 | 2.639 | 2.645 | 3.670 |
| AR(p) | 1.164 | 1.543 | 1.968 | 2.949 |
| **ARIMA** | **1.164** | **1.504** | **1.910** | **2.641** |
| ETS | 1.186 | 1.561 | 2.022 | 2.890 |
| Chronos-2 zero-shot | 1.218 | 1.596 | 2.073 | 2.924 |

ARIMA is the best classical baseline. Zero-shot Chronos-2 does not beat it.

## Current to-dos

- [ ] Add `ANTHROPIC_API_KEY` to `.env` for the search loop
- [ ] Run search loop (first experiment — see EXPERIMENT-1.md)
- [ ] Test Chronos-2 with manual covariate selections
- [ ] Run baselines on test era (2016+) for Phase 5 comparison
- [ ] Discuss with Leif: results so far, variable panel, division of labor

## Key design decisions

- Start with Chronos-2, keep model-agnostic
- Monthly macro panel as starting point
- Build own search loop inspired by autoresearch, not a direct fork
- Rolling pseudo-out-of-sample validation
- LLM-guided search (Claude Sonnet via API) for config proposals
- Subsample origins during search for speed (20 quick → 120 full)

## Known data limitations

- Industrial production (table 14208) ends 2023M12 — table appears discontinued at SSB
- Unemployment (table 13760) only from 2006M01 — no pre-2006 data
- House prices (seasonally adjusted) only from 2005Q1
- NOK/EUR only from 1999 (euro introduction)
