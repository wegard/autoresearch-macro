# prepare.py — Data Pipeline Specification

> **Status:** Spec for Claude Code implementation
> **Author:** Astra
> **Date:** 2026-03-27
> **Context:** This is the locked data pipeline for the autoresearch-macro project. The search agent cannot modify this file. It downloads, processes, and serves Norwegian and global macro data with pseudo-real-time discipline.

---

## 1. Role in the system

`prepare.py` is the equivalent of Karpathy's `prepare.py` — it provides data and evaluation infrastructure that the search agent cannot touch. It must:

1. Download and cache macro time series from SSB and global sources
2. Enforce pseudo-real-time data discipline (no future information at any forecast origin)
3. Provide a clean API for `train.py` to access data
4. Provide frozen evaluation functions for `evaluate.py`

---

## 2. Data sources

### 2.1 Norwegian macro series (SSB)

Use the SSB API (JSON-stat format, `https://data.ssb.no/api/v0/`).

**Target variables (monthly):**

| Variable              | SSB table | Series description                                   |
| --------------------- | --------- | ---------------------------------------------------- |
| CPI                   | 14700     | Consumer price index, total, 12-month change         |
| Industrial production | 14208     | Industrial production index, seasonally adjusted     |
| Retail sales          | 07129     | Retail sales index, seasonally adjusted              |
| House prices          | 07221     | House price index for existing dwellings (quarterly) |
| Credit                | 11599     | Domestic loan debt (C2-related), seasonally adjusted |
| Exports               | 08799     | External trade in goods, exports                     |
| Imports               | 08799     | External trade in goods, imports                     |

> **Note to implementer:** SSB table IDs should be verified — some may have changed. The API endpoint is `https://data.ssb.no/api/v0/en/table/<table_id>`. Use POST requests with JSON-stat query format.

**Additional Norwegian series:**

| Variable            | Source                            | Description                                |
| ------------------- | --------------------------------- | ------------------------------------------ |
| Policy rate         | Norges Bank API                   | Key policy rate                            |
| NOK/EUR             | Norges Bank API                   | Exchange rate                              |
| NOK/USD             | Norges Bank API                   | Exchange rate                              |
| PMI                 | DNB Markets / NIMA                 | Purchasing managers index (if available)   |
| Consumer confidence | Kantar / Opinion / Finance Norway | Consumer confidence indicator              |
| Unemployment        | NAV / SSB                         | Registered unemployed, seasonally adjusted |

### 2.2 Global series (FRED / public APIs)

| Variable | FRED series ID | Description |
|----------|---------------|-------------|
| Brent crude | DCOILBRENTEU | Brent crude oil price, daily → monthly avg |
| S&P 500 | SP500 | S&P 500 index, daily → monthly avg |
| Fed funds rate | FEDFUNDS | Effective federal funds rate |
| US CPI | CPIAUCSL | US CPI, all items |
| Euro area GDP | CLVMNACSCAB1GQEA19 | Euro area real GDP (quarterly, interpolated) |
| VIX | VIXCLS | CBOE VIX, daily → monthly avg |
| Global EPU | GEPUCURRENT | Global economic policy uncertainty |

### 2.3 Publication lags

Each series has a known publication lag. This is critical for pseudo-real-time validity.

```python
PUBLICATION_LAGS = {
    # Norwegian
    "cpi": 10,              # ~10 days after month end
    "unemployment": 30,     # ~1 month lag
    "industrial_production": 40,  # ~40 days
    "retail_sales": 30,
    "house_prices": 45,     # quarterly with ~45 day lag
    "credit": 40,
    "exports": 40,
    "imports": 40,
    "policy_rate": 0,       # known in real time
    "nok_eur": 1,           # next business day
    "nok_usd": 1,

    # Global
    "brent_crude": 1,
    "sp500": 1,
    "fed_funds": 1,
    "us_cpi": 15,
    "vix": 1,
    "global_epu": 30,
}
```

> **Note:** These are approximate. Vegard will refine based on actual SSB release calendars. The implementer should make these configurable via a YAML config, not hardcoded.

---

## 3. Data processing

### 3.1 Frequency alignment

All series aligned to monthly frequency.
- Daily series: monthly average
- Quarterly series: interpolated to monthly (linear or Denton method) or kept as last-known-value with appropriate lag
- Annual series: not included in v1

### 3.2 Transformations

`prepare.py` should provide raw series. Transformations are the search agent's job (via `train.py`). However, prepare.py should offer utility functions:

```python
def log_diff(series: pd.Series) -> pd.Series:
    """Log first difference (growth rate approximation)."""

def pct_change(series: pd.Series, periods: int = 12) -> pd.Series:
    """Year-over-year percentage change."""

def standardize(series: pd.Series, window: int = 60) -> pd.Series:
    """Rolling z-score standardization."""

def ma(series: pd.Series, window: int = 3) -> pd.Series:
    """Simple moving average."""
```

These are provided as a library for `train.py` to use — they don't transform the stored data.

### 3.3 Output format

Data stored as a single Parquet file per vintage (or a single file with date columns if vintages are unavailable):

```python
@dataclass
class MacroPanel:
    """The core data object."""
    data: pd.DataFrame          # index=date (monthly), columns=variable names
    metadata: dict               # variable descriptions, sources, units
    publication_lags: dict       # variable -> lag in days
    first_available: dict        # variable -> first date with data
    last_updated: datetime       # when this panel was last refreshed

    def available_at(self, forecast_origin: date) -> pd.DataFrame:
        """Return only data available at the given forecast origin,
        respecting publication lags. This is the key pseudo-real-time method."""

    def targets(self) -> list[str]:
        """Return list of target variable names."""

    def covariates(self) -> list[str]:
        """Return list of all available covariate names."""
```

The `available_at()` method is the critical piece. At any forecast origin date, it returns a DataFrame where each series is truncated to the last observation that would have been published by that date.

---

## 4. Caching

```
data/
├── raw/
│   ├── ssb/              # raw JSON-stat responses
│   └── fred/             # raw FRED CSV downloads
├── processed/
│   └── macro_panel.parquet   # processed monthly panel
└── metadata.json          # variable catalog, last download timestamps
```

- First run downloads everything from APIs
- Subsequent runs check `metadata.json` for staleness (re-download if >7 days old)
- Cache in `data/` directory (gitignored)

---

## 5. Validation / evaluation support

`prepare.py` provides the evaluation protocol used by `evaluate.py`:

```python
@dataclass
class ForecastOrigin:
    """A single forecast evaluation point."""
    origin_date: date           # the "as-of" date
    available_data: pd.DataFrame  # data available at origin
    actuals: dict[str, pd.Series]  # actual values for horizons 1,3,6,12

@dataclass
class EvaluationProtocol:
    """Rolling pseudo-out-of-sample evaluation."""
    origins: list[ForecastOrigin]
    horizons: list[int]         # [1, 3, 6, 12] months
    targets: list[str]          # which variables to forecast
    metrics: list[str]          # ["rmse", "mae", "mase", "pinball"]

def build_validation_origins(
    panel: MacroPanel,
    start: str = "2006-01",
    end: str = "2015-12",
    step_months: int = 1,
) -> list[ForecastOrigin]:
    """Generate rolling forecast origins for the validation era."""

def build_test_origins(
    panel: MacroPanel,
    start: str = "2016-01",
    end: str = None,  # latest available
    step_months: int = 1,
) -> list[ForecastOrigin]:
    """Generate rolling forecast origins for the test era. FROZEN — no search."""

def evaluate_forecasts(
    forecasts: dict[str, pd.DataFrame],  # variable -> DataFrame of forecasts
    origins: list[ForecastOrigin],
    horizons: list[int],
) -> dict:
    """Compute all metrics. Returns structured results."""
```

### Metrics

```python
def rmse(actual, predicted) -> float:
def mae(actual, predicted) -> float:
def mase(actual, predicted, naive_errors) -> float:
def pinball_loss(actual, quantiles, quantile_levels) -> float:
    """Weighted quantile loss for probabilistic forecasts."""
```

---

## 6. CLI interface

```bash
# Download and process all data
python src/prepare.py

# Download only, no processing
python src/prepare.py --download-only

# Force re-download even if cache is fresh
python src/prepare.py --force

# Show data summary
python src/prepare.py --info

# Verify pseudo-real-time discipline
python src/prepare.py --verify-realtime 2010-06-01
```

---

## 7. Dependencies

```
pandas>=2.0
pyarrow
requests
pyjstat          # for SSB JSON-stat format
fredapi          # for FRED API (requires API key via env var FRED_API_KEY)
```

---

## 8. Environment variables

```
FRED_API_KEY     # required for FRED data download
SSB_API_BASE     # optional, defaults to https://data.ssb.no/api/v0/en/table
DATA_DIR         # optional, defaults to ./data
```

---

## 9. Implementation notes

- SSB API uses POST with JSON-stat query bodies. The `pyjstat` library handles this.
- FRED API requires a free API key from <https://fred.stlouisfed.org/docs/api/api_key.html>
- Norges Bank has a public API for exchange rates and policy rate data.
- Publication lags should be configurable via `configs/publication_lags.yml` so Vegard can refine them.
- All dates are end-of-month convention (2010-01 means 2010-01-31).
- Missing values: forward-fill within series (last known value), never backfill.
- The `available_at()` method is the single source of truth for pseudo-real-time. Every data access in `train.py` and `evaluate.py` must go through it.

---

## 10. Testing requirements

```python
# tests/test_prepare.py

def test_panel_loads():
    """Panel loads without errors, has expected columns."""

def test_available_at_respects_lags():
    """Data at forecast origin t does not include series published after t."""

def test_available_at_no_future_leakage():
    """No variable has observations beyond what's available at the origin."""

def test_transformation_utilities():
    """log_diff, pct_change, standardize, ma produce correct output."""

def test_validation_origins():
    """Correct number of origins, correct date range."""

def test_evaluation_metrics():
    """RMSE, MAE, MASE, pinball on known inputs."""

def test_download_caching():
    """Second run uses cache, doesn't re-download."""
```

---

## 11. Open items for Vegard

- [x] Verify SSB table IDs — some may have changed or been replaced
- [ ] Refine publication lags from actual SSB release calendars
- [ ] Decide on Norges Bank API vs scraping for policy rate history
- [x] FRED API key — set up and store securely - Done: added to .env
- [ ] Vintage databases — if SSB provides revision history, integrate it
- [ ] Consumer confidence source — which provider has the longest monthly history?
