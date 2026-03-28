# Plan: Interactive Research Dashboard

## Vision

A modern, interactive web application that communicates the autoresearch-macro project: what we're doing, how it works, and what we've found. Built with **Quarto** for narrative structure and **D3.js** / **Observable Plot** for interactive visualizations. Designed to serve as both a research companion (live results as experiments run) and a public-facing project page.

---

## Architecture

```
webapp/
├── _quarto.yml              # Quarto project config (website type)
├── index.qmd                # Landing page — project overview
├── data-pipeline.qmd        # The data: sources, variables, pseudo-real-time
├── baselines.qmd            # Classical baselines and what they tell us
├── foundation-model.qmd     # Chronos-2: zero-shot → fine-tuned → agent-tuned
├── search.qmd               # The search loop: trajectory, discoveries, analysis
├── results.qmd              # Full comparison table, test era results
├── methodology.qmd          # Technical methodology for the paper-minded reader
├── _components/
│   ├── forecast-comparison.js    # D3 interactive method comparison chart
│   ├── search-trajectory.js      # D3 animated search iteration timeline
│   ├── variable-explorer.js      # D3 time series explorer with real-time cutoff
│   ├── heatmap-table.js          # D3 color-coded metrics heatmap
│   └── horizon-slider.js         # Reusable horizon selector component
├── _data/
│   ├── prepare_results.py        # Script: reads parquet/JSON → writes JSON for D3
│   └── (generated .json files)   # Pre-processed data consumed by D3
├── styles.css                    # Custom styling
└── _extensions/                  # Quarto extensions if needed
```

**Stack:** Quarto (website project) + D3.js (custom interactive charts) + Observable Plot (quick exploratory charts) + OJS cells in .qmd files for reactive data binding.

---

## Pages and visualizations

### 1. Landing page (`index.qmd`)

**Purpose:** Hook the reader. State the research question. Show the headline result.

**Content:**
- One-paragraph summary of the project
- Hero visualization: animated bar chart showing how the search agent's score evolves over iterations, converging below the ARIMA baseline (or not — the honest result)
- Key numbers: 18 variables, 120 forecast origins, N search iterations, best score
- Navigation to deeper pages

**Visualizations:**
- **Hero chart** (D3): Animated step-line showing search score over iterations, with ARIMA baseline as a horizontal reference line. Points color-coded by accepted/rejected.

### 2. The data (`data-pipeline.qmd`)

**Purpose:** Explain what data we use and how pseudo-real-time discipline works.

**Content:**
- Data sources table (SSB, FRED, Norges Bank) with descriptions
- Variable coverage timeline — when each series starts/ends
- Publication lags and why they matter
- Interactive demo of the `available_at()` mechanism

**Visualizations:**
- **Variable timeline** (D3): Horizontal bar chart showing date range per variable, color-coded by source (SSB blue, FRED red, Norges Bank green). Hover for details.
- **Pseudo-real-time explorer** (D3): User picks a forecast origin date via slider. Chart shows which data points are "visible" vs "hidden" for each variable, illustrating publication lags. The cutoff line moves as you slide.
- **Data heatmap** (D3/Observable Plot): Monthly heatmap of data availability (18 variables × time). Color intensity = value, white = missing.

**Data prep:** `macro_panel.parquet` → JSON time series. `panel_meta.json` provides descriptions and lags.

### 3. Baselines (`baselines.qmd`)

**Purpose:** Establish what standard methods achieve. Explain why beating them matters.

**Content:**
- Brief description of each method (random walk, seasonal naive, AR, ARIMA, ETS)
- Interactive comparison across methods, variables, and horizons
- Key insight: ARIMA is the strongest, random walk is surprisingly hard to beat at long horizons

**Visualizations:**
- **Metric comparison heatmap** (D3): Rows = methods, columns = variable×horizon. Cell color = RMSE (green = good, red = bad). Click a cell to see the forecast vs actual time series.
- **Horizon profile chart** (D3): For each method, line chart of RMSE vs horizon. Shows how errors grow with forecast distance. Toggle between variables.
- **Relative performance bar chart** (D3): Each method's RMSE relative to random walk (ratio < 1 = better). Grouped by horizon. Makes it immediately clear which methods add value.

**Data prep:** `results/validation/*/metrics.json` → combined JSON.

### 4. Foundation model (`foundation-model.qmd`)

**Purpose:** Show what Chronos-2 brings and how adaptation helps (or doesn't).

**Content:**
- What is Chronos-2? Brief explainer with architecture diagram
- Zero-shot results: does a pretrained model know anything about Norwegian macro?
- Effect of covariates: what happens when we add oil prices, exchange rates?
- Effect of fine-tuning: does economy-specific training help?
- The gap between zero-shot and ARIMA — this is what the search agent needs to close

**Visualizations:**
- **Foundation model ladder** (D3): Stacked comparison showing zero-shot → +covariates → +fine-tuning → +agent-tuned. Each step shows the incremental gain (or loss). The three-way ablation from DESIGN.md.
- **Forecast fan chart** (D3): For a selected variable and origin, show the actual series, the forecast distribution (quantiles as shaded bands), and the point forecast. Slider to change origin date.
- **Covariate importance** (D3): If search results show which covariates help, bar chart of frequency each covariate appears in accepted configs.

### 5. The search (`search.qmd`)

**Purpose:** The core story — what did the agent try, what did it learn, what worked?

**Content:**
- How the search loop works (diagram)
- Search trajectory: score over iterations
- What the agent tried: covariates, transforms, fine-tuning
- Patterns: did it converge? Did it find interpretable configurations?
- Comparison to manual tuning (if available)

**Visualizations:**
- **Search trajectory** (D3, animated): Main chart. X = iteration, Y = score (MASE). Each point is an iteration, colored green (accepted) or red (rejected). Line connects accepted points showing the "frontier." Hover for config details. Play/pause animation.
- **Config evolution** (D3): Parallel coordinates or matrix showing how each config dimension (covariates, transforms, context_length, etc.) changes across accepted iterations. Shows the agent's "path" through config space.
- **Covariate frequency** (D3): Stacked area chart showing which covariates are included over time. Reveals which variables the agent considers important.
- **Score decomposition** (D3): Small multiples — one panel per target variable showing how the agent's score on each variable evolves. Some variables may improve while others get worse.

**Data prep:** `results/search_log.jsonl` → JSON array. `results/search_state.json` for final state.

### 6. Results (`results.qmd`)

**Purpose:** The definitive comparison table for the paper.

**Content:**
- Full results table (all methods × all variables × all horizons × all metrics)
- Test era results (2016+) with subperiod breakdown
- Statistical significance (Diebold-Mariano tests if implemented)
- Summary of findings

**Visualizations:**
- **Grand comparison table** (D3): Interactive sortable table with color coding. Filter by metric, sort by any column. Highlight the best method per cell.
- **Subperiod analysis** (D3): For the test era, show results by subperiod (pre-COVID, COVID, post-COVID). Grouped bar chart or heatmap. Shows which methods are robust to regime changes.
- **Cumulative forecast error** (D3): Time series of cumulative absolute error for each method across the test period. Methods that struggle during COVID will show a visible jump.

### 7. Methodology (`methodology.qmd`)

**Purpose:** Technical details for researchers who want to understand or replicate.

**Content:**
- Evaluation protocol (rolling expanding window, pseudo-real-time)
- Metrics definitions (RMSE, MAE, MASE, pinball loss)
- Search loop design and hyperparameters
- Chronos-2 model details and AutoGluon interface
- Reproducibility notes (seeds, configs, data versions)

**Visualizations:**
- **Evaluation protocol diagram** (D3 or static SVG): Rolling window illustration showing training data, validation origin, forecast horizons.
- **Publication lag diagram** (static): Timeline showing how different variables become available at different delays.

---

## Data pipeline (`_data/prepare_results.py`)

Script that reads the project's native data formats and writes JSON files for D3:

```python
# Reads:
#   results/validation/*/metrics.json   → combined_metrics.json
#   results/validation/*/config.json    → method_configs.json
#   results/search_log.jsonl            → search_trajectory.json
#   data/processed/macro_panel.parquet  → panel_timeseries.json (sampled)
#   data/processed/panel_meta.json      → variable_metadata.json

# Writes:
#   _data/combined_metrics.json
#   _data/method_configs.json
#   _data/search_trajectory.json
#   _data/panel_timeseries.json
#   _data/variable_metadata.json
```

Run before `quarto render`: `uv run python webapp/_data/prepare_results.py`

---

## Tech choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Site generator | **Quarto** (website project) | Native support for OJS/D3, computes Python/R inline, great for academic work |
| Charting (custom) | **D3.js v7** | Full control for the key interactive visualizations |
| Charting (quick) | **Observable Plot** | Rapid creation of standard statistical charts via OJS cells |
| Reactivity | **OJS cells** in Quarto | Built-in reactive programming — inputs (sliders, dropdowns) drive chart updates without custom JS |
| Styling | **Custom CSS** + Quarto themes | Clean, modern look. Consider `cosmo` or `flatly` Quarto theme |
| Hosting | **GitHub Pages** or **Quarto Pub** | Free, static, no server needed |
| Data format | **JSON** (pre-processed from Parquet/JSONL) | D3 native, small enough for client-side |

---

## Implementation order

### Phase A: Skeleton (1 session)

1. Initialize Quarto website project in `webapp/`
2. Create `_quarto.yml` with navigation, theme, D3/OJS setup
3. Create stub `.qmd` files for all pages with placeholder content
4. Write `_data/prepare_results.py` to export current results as JSON
5. Build and verify: `quarto preview webapp/`

### Phase B: Data and baselines pages (1-2 sessions)

6. Build the variable timeline visualization (D3)
7. Build the pseudo-real-time explorer (D3 + OJS slider)
8. Build the metric comparison heatmap (D3)
9. Build the horizon profile chart (D3)
10. Write narrative content for data-pipeline.qmd and baselines.qmd

### Phase C: Foundation model and search pages (1-2 sessions)

11. Build the foundation model ladder chart (D3)
12. Build the forecast fan chart (D3 + OJS origin selector)
13. Build the search trajectory visualization (D3, animated)
14. Build the config evolution chart (D3 parallel coordinates)
15. Write narrative content for foundation-model.qmd and search.qmd

### Phase D: Results and polish (1 session)

16. Build the grand comparison table (D3 interactive table)
17. Build subperiod analysis charts
18. Write results.qmd and methodology.qmd content
19. Design the landing page hero visualization
20. Final styling, responsive layout, testing

### Phase E: Deployment

21. Set up GitHub Pages or Quarto Pub deployment
22. Add `quarto render` to project Makefile or CI
23. Write update instructions (re-run `prepare_results.py` after new experiments)

---

## Design principles

- **Narrative first:** Each page tells a story. Visualizations support the argument, not the other way around.
- **Progressive disclosure:** Start with the headline, let users drill down. Summaries → per-variable → per-origin.
- **Honest results:** If the agent doesn't beat ARIMA, show that clearly. Negative results are valuable.
- **Reproducible:** All data flows from the project's results/ and data/ directories through prepare_results.py. No manual data entry.
- **Responsive:** Works on laptop screens (primary audience: academic seminars, reviewers).

---

## Dependencies to add

```bash
# Quarto (install separately, not via pip)
# https://quarto.org/docs/get-started/

# No additional Python deps needed — prepare_results.py uses pandas/json already in the project
```

Quarto handles D3.js and Observable Plot via its built-in OJS engine. No npm/node setup needed.
