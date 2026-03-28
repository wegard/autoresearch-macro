# Decision Log

## 2026-03-27 — Project setup

**Decision:** Create project workspace, build own search loop rather than forking autoresearch.

**Reasoning:** Karpathy's autoresearch is designed for single-GPU vision/language tasks with a single train.py. We need a forecasting-specific loop with rolling validation, structured search space, and Chronos-2/AutoGluon backend. Clone for reference, build our own.

**Decision:** Start with Chronos-2 specifically, but design the search loop model-agnostic from day one.

**Reasoning:** Chronos-2 has native covariate support and probabilistic output — good starting point. But the stronger paper tests whether agentic search generalizes across foundation models.

**Decision:** Monthly macro panel as initial target set.

**Reasoning:** More data points than quarterly, cleaner evaluation, natural starting point. Quarterly GDP / mixed-frequency are extensions.

## 2026-03-28 — Implementation sprint

**Decision:** Replace 3 SSB table IDs after live API verification.

**Reasoning:** Original table IDs were guesses from the spec. Verification revealed: 01598 (unemployment) returns 400, 13967 was election data not unemployment, 08799 (trade) had 13k commodity codes. Replaced with: 13760 (LFS unemployment), 08803 (trade main figures). Also fixed Norges Bank policy rate SDMX key.

**Decision:** Switch from FRED SP500 to NASDAQCOM for stock market proxy.

**Reasoning:** FRED restricts SP500 to ~10 years of data. NASDAQCOM goes back to 1971, sufficient for pre-2006 training window.

**Decision:** Use AutoGluon TimeSeriesPredictor (not raw ChronosPipeline) as the model interface.

**Reasoning:** ChronosPipeline had version compatibility issues (`input_patch_size` config error). AutoGluon wraps Chronos cleanly with fit-once-predict-many pattern.

**Decision:** Default model size: chronos-bolt-small (~20M params).

**Reasoning:** Fits in 2GB VRAM, fast inference (~1.3s per origin). Good for search iterations where speed matters. Can upgrade to bolt-base for final evaluation.

**Decision:** LLM-guided search (not structured random search) as the primary search strategy.

**Reasoning:** The paper's contribution is specifically about agentic search. Structured search can serve as a comparison baseline but is not the core experiment.

**Decision:** Two-phase evaluation during search: quick (20 origins) → full (120 origins).

**Reasoning:** Full evaluation takes ~3 minutes. Quick evaluation takes ~30 seconds. Only run full eval when quick eval shows improvement. Dramatically increases iteration speed.

**Decision:** Use MASE as the primary search metric (not RMSE).

**Reasoning:** MASE is scale-independent (each variable's error is normalized by the naive forecast error). This prevents the search from over-optimizing for the variable with the largest scale.
