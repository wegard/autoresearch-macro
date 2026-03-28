"""
Data pipeline for the autoresearch-macro project.

Downloads Norwegian and global macro data, handles frequency alignment
and publication lags, and provides pseudo-real-time data access via the
MacroPanel dataclass.

This file is LOCKED — the search agent cannot modify it.

Usage:
    python src/prepare.py                          # Download and process all data
    python src/prepare.py --download-only          # Download only, no panel build
    python src/prepare.py --force                  # Force re-download even if cache is fresh
    python src/prepare.py --info                   # Show data summary
    python src/prepare.py --verify-realtime 2010-06-01  # Verify pseudo-real-time discipline
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR", str(PROJECT_ROOT / "data")))
RAW_SSB_DIR = DATA_DIR / "raw" / "ssb"
RAW_FRED_DIR = DATA_DIR / "raw" / "fred"
RAW_NB_DIR = DATA_DIR / "raw" / "norges_bank"
PROCESSED_DIR = DATA_DIR / "processed"
METADATA_PATH = DATA_DIR / "metadata.json"
CONFIGS_DIR = PROJECT_ROOT / "configs"

SSB_API_BASE = os.environ.get("SSB_API_BASE", "https://data.ssb.no/api/v0/en/table")
NORGES_BANK_API_BASE = "https://data.norges-bank.no/api/data"
CACHE_MAX_AGE_DAYS = 7

HORIZONS: list[int] = [1, 3, 6, 12]

TARGET_VARIABLES: list[str] = [
    "cpi",
    "industrial_production",
    "retail_sales",
    "unemployment",
]

ALL_VARIABLES: list[str] = TARGET_VARIABLES + [
    "house_prices",
    "credit",
    "exports",
    "imports",
    "policy_rate",
    "nok_eur",
    "nok_usd",
    "brent_crude",
    "sp500",
    "fed_funds",
    "us_cpi",
    "vix",
    "global_epu",
    "euro_area_gdp",
]

# ---------------------------------------------------------------------------
# Publication lags
# ---------------------------------------------------------------------------


def load_publication_lags() -> dict[str, int]:
    """Load publication lags (in days) from configs/publication_lags.yml."""
    lag_file = CONFIGS_DIR / "publication_lags.yml"
    if lag_file.exists():
        with open(lag_file) as f:
            lags = yaml.safe_load(f)
        return {k: int(v) for k, v in lags.items()}
    logger.warning("publication_lags.yml not found, using built-in defaults")
    return _default_publication_lags()


def _default_publication_lags() -> dict[str, int]:
    """Fallback if config file is missing."""
    return {
        "cpi": 10, "unemployment": 30, "industrial_production": 40,
        "retail_sales": 30, "house_prices": 45, "credit": 40,
        "exports": 40, "imports": 40, "policy_rate": 0,
        "nok_eur": 1, "nok_usd": 1, "brent_crude": 1, "sp500": 1,
        "fed_funds": 1, "us_cpi": 15, "vix": 1, "global_epu": 30,
        "euro_area_gdp": 90,
    }


# ---------------------------------------------------------------------------
# SSB series configuration
# ---------------------------------------------------------------------------

# Table IDs verified against live SSB API on 2026-03-28.
# Each entry uses explicit `selections` for all non-time dimensions
# to avoid fragile auto-selection of the first value.
SSB_SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "cpi": {
        "table_id": "03013",
        "description": "Consumer price index, 12-month rate of change (%)",
        "selections": {
            "Konsumgrp": ["TOTAL"],
            "ContentsCode": ["Tolvmanedersendring"],
        },
        "frequency": "monthly",
    },
    "industrial_production": {
        "table_id": "14208",
        "description": "Manufacturing production index, seasonally adjusted (2005=100)",
        "selections": {
            "PKoder": ["P105"],
            "ContentsCode": ["Sesongjustert"],
        },
        "frequency": "monthly",
        # NOTE: Table 14208 ends 2023M12 as of 2026-03-28.
    },
    "retail_sales": {
        "table_id": "07129",
        "description": "Retail trade volume index, seasonally adjusted",
        "selections": {
            "NACE": ["47"],
            "ContentsCode": ["VolumSesong"],
        },
        "frequency": "monthly",
    },
    "house_prices": {
        "table_id": "07221",
        "description": "House price index, seasonally adjusted (existing dwellings)",
        "selections": {
            "Region": ["TOTAL"],
            "Boligtype": ["00"],
            "ContentsCode": ["SesJustBoligindeks"],
        },
        "frequency": "quarterly",
    },
    "credit": {
        "table_id": "11599",
        "description": "Domestic credit (C2), 12-month growth (%)",
        "selections": {
            "Valuta": ["00"],
            "Lantaker2": ["Kred01"],
            "ContentsCode": ["AarsTrans2"],
        },
        "frequency": "monthly",
    },
    "exports": {
        "table_id": "08803",
        "description": "Total exports of goods (NOK million), all countries",
        "selections": {
            "HovedVareStrommer": ["Etot"],
            "Land": ["00"],
            "ContentsCode": ["Verdi"],
        },
        "frequency": "monthly",
    },
    "imports": {
        "table_id": "08803",
        "description": "Total imports of goods (NOK million), all countries",
        "selections": {
            "HovedVareStrommer": ["Itot"],
            "Land": ["00"],
            "ContentsCode": ["Verdi"],
        },
        "frequency": "monthly",
    },
    "unemployment": {
        "table_id": "13760",
        "description": "Unemployment rate (LFS), seasonally adjusted, 15-74 years",
        "selections": {
            "Kjonn": ["0"],
            "Alder": ["15-74"],
            "Justering": ["S"],
            "ContentsCode": ["ArbledProsArbstyrk"],
        },
        "frequency": "monthly",
        # NOTE: Table 13760 starts 2006M01 (no pre-2006 data).
    },
}

# FRED series configuration
FRED_SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "brent_crude": {
        "series_id": "DCOILBRENTEU",
        "description": "Brent crude oil price, daily → monthly avg",
        "frequency": "daily",
    },
    "sp500": {
        # FRED SP500 only has ~10 years of data (restricted).
        # NASDAQCOM goes back to 1971 and is a standard stock market proxy.
        "series_id": "NASDAQCOM",
        "description": "NASDAQ Composite index, daily → monthly avg",
        "frequency": "daily",
    },
    "fed_funds": {
        "series_id": "FEDFUNDS",
        "description": "Effective federal funds rate, monthly",
        "frequency": "monthly",
    },
    "us_cpi": {
        "series_id": "CPIAUCSL",
        "description": "US CPI, all items, monthly index",
        "frequency": "monthly",
    },
    "euro_area_gdp": {
        "series_id": "CLVMNACSCAB1GQEA19",
        "description": "Euro area real GDP, quarterly",
        "frequency": "quarterly",
    },
    "vix": {
        "series_id": "VIXCLS",
        "description": "CBOE VIX, daily → monthly avg",
        "frequency": "daily",
    },
    "global_epu": {
        "series_id": "GEPUCURRENT",
        "description": "Global economic policy uncertainty, monthly",
        "frequency": "monthly",
    },
}

# Norges Bank series configuration
NORGES_BANK_CONFIG: dict[str, dict[str, Any]] = {
    "nok_eur": {
        "flow": "EXR",
        "key": "B.EUR.NOK.SP",
        "description": "NOK/EUR exchange rate, daily → monthly avg",
        "frequency": "daily",
    },
    "nok_usd": {
        "flow": "EXR",
        "key": "B.USD.NOK.SP",
        "description": "NOK/USD exchange rate, daily → monthly avg",
        "frequency": "daily",
    },
    "policy_rate": {
        # Verified 2026-03-28: B.KPRA.. returns daily key policy rate.
        "flow": "IR",
        "key": "B.KPRA..",
        "description": "Norges Bank key policy rate",
        "frequency": "daily",
    },
}


# ---------------------------------------------------------------------------
# SSB download functions
# ---------------------------------------------------------------------------


def _parse_ssb_time(time_str: str) -> pd.Timestamp:
    """Parse SSB time format into end-of-period Timestamp.

    Examples:
        '2020M01' → 2020-01-31
        '2020K1'  → 2020-03-31
        '2020'    → 2020-12-31
    """
    if "M" in time_str:
        year, month = time_str.split("M")
        return pd.Timestamp(int(year), int(month), 1) + pd.offsets.MonthEnd(0)
    elif "K" in time_str:
        year, quarter = time_str.split("K")
        month = int(quarter) * 3
        return pd.Timestamp(int(year), month, 1) + pd.offsets.MonthEnd(0)
    else:
        return pd.Timestamp(int(time_str), 12, 31)


def _parse_jsonstat2(data: dict) -> pd.Series:
    """Parse a JSON-stat2 response into a pd.Series with DatetimeIndex.

    Assumes all non-time dimensions have been filtered to a single value
    so the result is a 1-D time series.
    """
    dim_ids: list[str] = data["id"]
    sizes: list[int] = data["size"]
    values: list = data.get("value", [])

    # Find time dimension
    time_dim: str | None = None
    for d in dim_ids:
        if d.lower() in ("tid", "time", "måned", "kvartal"):
            time_dim = d
            break
    if time_dim is None:
        time_dim = dim_ids[-1]

    time_idx = dim_ids.index(time_dim)
    cat = data["dimension"][time_dim]["category"]
    index_map: dict[str, int] = cat.get("index", {})
    label_map: dict[str, str] = cat.get("label", {})
    codes = sorted(index_map.keys(), key=lambda k: index_map[k])
    labels = [label_map.get(c, c) for c in codes]
    dates = [_parse_ssb_time(lbl) for lbl in labels]

    # Check that non-time dimensions are all size 1
    n_time = sizes[time_idx]
    non_time_product = 1
    for i, s in enumerate(sizes):
        if i != time_idx:
            non_time_product *= s

    if non_time_product != 1:
        logger.warning(
            "Expected 1-D result but got %d non-time combinations; taking first slice.",
            non_time_product,
        )
    # In C-order, if time is the last dim, values[:n_time] is the first slice.
    # If time is not last, we need to stride. For simplicity, assume the query
    # was constructed to produce a 1-D result (non_time_product == 1).
    vals = values[:n_time]

    series = pd.Series(
        [float(v) if v is not None else np.nan for v in vals],
        index=pd.DatetimeIndex(dates, name="date"),
        dtype=float,
    )
    return series.sort_index()


def download_ssb_series(name: str, config: dict[str, Any]) -> pd.Series | None:
    """Download a single series from the SSB API.

    Args:
        name: Internal variable name.
        config: Entry from SSB_SERIES_CONFIG.

    Returns:
        Monthly pd.Series or None on failure.
    """
    table_id = config["table_id"]
    selections = config.get("selections", {})
    url = f"{SSB_API_BASE}/{table_id}"

    try:
        # Step 1: fetch metadata to learn table structure
        logger.info("Fetching SSB metadata for table %s (%s)...", table_id, name)
        meta_resp = requests.get(url, timeout=30)
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        # Step 2: build query — use explicit selections where provided,
        # otherwise select first value for non-time dimensions.
        query_dims: list[dict] = []
        for var in meta.get("variables", []):
            code = var["code"]
            values = var.get("values", [])

            if code.lower() in ("tid", "time", "måned", "kvartal", "år"):
                query_dims.append({
                    "code": code,
                    "selection": {"filter": "all", "values": ["*"]},
                })
            elif code in selections:
                query_dims.append({
                    "code": code,
                    "selection": {"filter": "item", "values": selections[code]},
                })
            elif values:
                # Fallback: select first value (usually "total" or aggregate)
                query_dims.append({
                    "code": code,
                    "selection": {"filter": "item", "values": [values[0]]},
                })

        query = {"query": query_dims, "response": {"format": "json-stat2"}}

        # Step 3: download
        logger.info("Downloading SSB table %s (%s)...", table_id, name)
        data_resp = requests.post(url, json=query, timeout=120)
        data_resp.raise_for_status()

        series = _parse_jsonstat2(data_resp.json())
        series.name = name

        # Step 4: handle frequency
        if config.get("frequency") == "quarterly":
            series = quarterly_to_monthly(series)

        # Cache raw response
        cache_dir = RAW_SSB_DIR / table_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{name}.json"
        cache_path.write_text(data_resp.text)

        logger.info("SSB %s: %d observations, %s to %s",
                     name, len(series), series.index[0].date(), series.index[-1].date())
        return series

    except Exception:
        logger.exception("Failed to download SSB series %s (table %s)", name, table_id)
        return None


def download_all_ssb(force: bool = False) -> dict[str, pd.Series]:
    """Download all configured SSB series. Returns {name: Series}."""
    results: dict[str, pd.Series] = {}
    for name, config in SSB_SERIES_CONFIG.items():
        if not force and _cache_is_fresh(f"ssb_{name}"):
            cached = _load_cached_series(f"ssb_{name}")
            if cached is not None:
                results[name] = cached
                continue
        series = download_ssb_series(name, config)
        if series is not None:
            results[name] = series
            _save_cached_series(f"ssb_{name}", series)
    return results


# ---------------------------------------------------------------------------
# Norges Bank download functions
# ---------------------------------------------------------------------------


def download_norges_bank_series(
    name: str, config: dict[str, Any]
) -> pd.Series | None:
    """Download a series from the Norges Bank SDMX API.

    Returns a monthly pd.Series or None on failure.
    """
    flow = config["flow"]
    key = config["key"]
    url = f"{NORGES_BANK_API_BASE}/{flow}/{key}"
    params = {
        "format": "sdmx-csv",
        "startPeriod": "1990-01-01",
        "endPeriod": "2026-12-31",
    }

    try:
        logger.info("Downloading Norges Bank %s (%s/%s)...", name, flow, key)
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()

        # Parse CSV response (SDMX-CSV has headers like TIME_PERIOD, OBS_VALUE)
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))

        # Find the right columns (SDMX-CSV column names vary)
        time_col = _find_column(df, ["TIME_PERIOD", "TIME", "Date"])
        value_col = _find_column(df, ["OBS_VALUE", "VALUE", "Value"])
        if time_col is None or value_col is None:
            logger.warning("Norges Bank %s: could not identify columns in %s",
                           name, list(df.columns))
            return None

        series = pd.Series(
            df[value_col].values,
            index=pd.to_datetime(df[time_col]),
            dtype=float,
            name=name,
        )
        series.index.name = "date"
        series = series.sort_index()

        # Aggregate to monthly if daily
        if config.get("frequency") == "daily":
            series = daily_to_monthly(series)

        # Cache
        cache_dir = RAW_NB_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{name}.csv").write_text(resp.text)

        logger.info("Norges Bank %s: %d monthly obs, %s to %s",
                     name, len(series), series.index[0].date(), series.index[-1].date())
        return series

    except Exception:
        logger.exception("Failed to download Norges Bank series %s", name)
        return None


def download_all_norges_bank(force: bool = False) -> dict[str, pd.Series]:
    """Download all configured Norges Bank series."""
    results: dict[str, pd.Series] = {}
    for name, config in NORGES_BANK_CONFIG.items():
        if not force and _cache_is_fresh(f"nb_{name}"):
            cached = _load_cached_series(f"nb_{name}")
            if cached is not None:
                results[name] = cached
                continue
        series = download_norges_bank_series(name, config)
        if series is not None:
            results[name] = series
            _save_cached_series(f"nb_{name}", series)
    return results


# ---------------------------------------------------------------------------
# FRED download functions
# ---------------------------------------------------------------------------


def download_fred_series(name: str, config: dict[str, Any]) -> pd.Series | None:
    """Download a single series from FRED.

    Requires FRED_API_KEY environment variable.
    """
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.warning("FRED_API_KEY not set — skipping %s", name)
        return None

    series_id = config["series_id"]

    try:
        from fredapi import Fred

        fred = Fred(api_key=api_key)
        logger.info("Downloading FRED %s (%s)...", name, series_id)
        raw: pd.Series = fred.get_series(series_id)
        raw.name = name
        raw.index.name = "date"
        raw = raw.dropna()

        # Frequency alignment — FRED dates may not be month-end,
        # so always snap to month-end first.
        freq = config.get("frequency", "monthly")
        if freq == "daily":
            series = daily_to_monthly(raw)
        elif freq == "quarterly":
            raw.index = raw.index + pd.offsets.MonthEnd(0)
            series = quarterly_to_monthly(raw)
        else:
            # Already monthly — snap to month-end
            series = raw.copy()
            series.index = series.index + pd.offsets.MonthEnd(0)
            series = series[~series.index.duplicated(keep="last")]

        series.name = name

        # Cache
        RAW_FRED_DIR.mkdir(parents=True, exist_ok=True)
        raw.to_csv(RAW_FRED_DIR / f"{name}.csv")

        logger.info("FRED %s: %d monthly obs, %s to %s",
                     name, len(series), series.index[0].date(), series.index[-1].date())
        return series

    except Exception:
        logger.exception("Failed to download FRED series %s (%s)", name, series_id)
        return None


def download_all_fred(force: bool = False) -> dict[str, pd.Series]:
    """Download all configured FRED series."""
    results: dict[str, pd.Series] = {}
    for name, config in FRED_SERIES_CONFIG.items():
        if not force and _cache_is_fresh(f"fred_{name}"):
            cached = _load_cached_series(f"fred_{name}")
            if cached is not None:
                results[name] = cached
                continue
        series = download_fred_series(name, config)
        if series is not None:
            results[name] = series
            _save_cached_series(f"fred_{name}", series)
    return results


# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------


def _load_metadata() -> dict:
    if METADATA_PATH.exists():
        return json.loads(METADATA_PATH.read_text())
    return {}


def _save_metadata(meta: dict) -> None:
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(meta, indent=2, default=str))


def _cache_is_fresh(key: str) -> bool:
    """Check if a cached series is younger than CACHE_MAX_AGE_DAYS."""
    meta = _load_metadata()
    ts = meta.get("last_download", {}).get(key)
    if ts is None:
        return False
    last = datetime.fromisoformat(ts)
    return (datetime.now() - last).days < CACHE_MAX_AGE_DAYS


def _save_cached_series(key: str, series: pd.Series) -> None:
    """Save a series to the processed cache and update metadata."""
    cache_dir = PROCESSED_DIR / "series_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    series.to_frame(name=series.name or key).to_parquet(cache_dir / f"{key}.parquet")
    meta = _load_metadata()
    meta.setdefault("last_download", {})[key] = datetime.now().isoformat()
    _save_metadata(meta)


def _load_cached_series(key: str) -> pd.Series | None:
    """Load a cached series."""
    path = PROCESSED_DIR / "series_cache" / f"{key}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    series = df.iloc[:, 0]
    series.name = df.columns[0]
    logger.info("Loaded cached %s (%d obs)", key, len(series))
    return series


# ---------------------------------------------------------------------------
# Frequency alignment
# ---------------------------------------------------------------------------


def daily_to_monthly(series: pd.Series) -> pd.Series:
    """Aggregate daily series to monthly by taking the mean.

    Result is indexed at month-end dates.
    """
    monthly = series.resample("ME").mean()
    monthly = monthly.dropna()
    monthly.name = series.name
    return monthly


def quarterly_to_monthly(series: pd.Series) -> pd.Series:
    """Expand quarterly series to monthly using forward-fill (last known value).

    This is the conservative approach: no interpolation, just carry the
    most recent quarterly observation forward until the next one arrives.
    """
    # Reindex to monthly end-of-period dates
    if series.empty:
        return series
    start = series.index.min()
    end = series.index.max()
    monthly_idx = pd.date_range(start=start, end=end, freq="ME")
    monthly = series.reindex(monthly_idx).ffill()
    monthly.name = series.name
    monthly.index.name = "date"
    return monthly


# ---------------------------------------------------------------------------
# Transformation utilities (library for train.py)
# ---------------------------------------------------------------------------


def log_diff(series: pd.Series) -> pd.Series:
    """Log first difference — approximation of growth rate."""
    result = np.log(series).diff()
    result.name = f"{series.name}_logdiff" if series.name else "logdiff"
    return result


def pct_change(series: pd.Series, periods: int = 12) -> pd.Series:
    """Year-over-year (or custom period) percentage change."""
    result = series.pct_change(periods=periods) * 100
    result.name = f"{series.name}_pct{periods}" if series.name else f"pct{periods}"
    return result


def standardize(series: pd.Series, window: int = 60) -> pd.Series:
    """Rolling z-score standardization."""
    roll_mean = series.rolling(window=window, min_periods=max(1, window // 2)).mean()
    roll_std = series.rolling(window=window, min_periods=max(1, window // 2)).std()
    result = (series - roll_mean) / roll_std.replace(0, np.nan)
    result.name = f"{series.name}_std" if series.name else "std"
    return result


def ma(series: pd.Series, window: int = 3) -> pd.Series:
    """Simple moving average."""
    result = series.rolling(window=window, min_periods=1).mean()
    result.name = f"{series.name}_ma{window}" if series.name else f"ma{window}"
    return result


# ---------------------------------------------------------------------------
# MacroPanel dataclass
# ---------------------------------------------------------------------------


@dataclass
class MacroPanel:
    """The core data object for pseudo-real-time macro forecasting.

    Attributes:
        data: Monthly DataFrame (index = end-of-month dates, columns = variable names).
        metadata: Variable descriptions, sources, units.
        publication_lags: Variable name → lag in days after end of reference period.
        first_available: Variable name → first date with data.
        last_updated: When this panel was last refreshed.
    """

    data: pd.DataFrame
    metadata: dict[str, Any]
    publication_lags: dict[str, int]
    first_available: dict[str, pd.Timestamp]
    last_updated: datetime

    def available_at(self, forecast_origin: date) -> pd.DataFrame:
        """Return only data available at the given forecast origin.

        For each variable, the publication lag determines how long after
        the end of the reference period the data becomes available.  An
        observation for month M (indexed at month-end) is available when:

            month_end(M) + publication_lag  ≤  forecast_origin

        This is the **single source of truth** for pseudo-real-time discipline.
        """
        origin = pd.Timestamp(forecast_origin)
        result: dict[str, pd.Series] = {}

        for col in self.data.columns:
            lag_days = self.publication_lags.get(col, 30)
            cutoff = origin - pd.Timedelta(days=lag_days)
            available = self.data[col].loc[self.data.index <= cutoff].dropna()
            if not available.empty:
                result[col] = available

        df = pd.DataFrame(result)
        return df

    def targets(self) -> list[str]:
        """Return list of target variable names present in the panel."""
        return [v for v in TARGET_VARIABLES if v in self.data.columns]

    def covariates(self) -> list[str]:
        """Return list of all available covariate names (non-target)."""
        return [c for c in self.data.columns if c not in TARGET_VARIABLES]

    def summary(self) -> str:
        """Human-readable summary of the panel."""
        lines = [
            f"MacroPanel — {len(self.data.columns)} variables, "
            f"{len(self.data)} months",
            f"  Date range: {self.data.index[0].date()} to {self.data.index[-1].date()}",
            f"  Last updated: {self.last_updated:%Y-%m-%d %H:%M}",
            f"  Targets: {', '.join(self.targets())}",
            f"  Covariates: {', '.join(self.covariates())}",
            "",
            "  Variable coverage:",
        ]
        for col in self.data.columns:
            non_null = self.data[col].notna().sum()
            first = self.data[col].first_valid_index()
            last = self.data[col].last_valid_index()
            first_str = first.date() if first is not None else "N/A"
            last_str = last.date() if last is not None else "N/A"
            lag = self.publication_lags.get(col, "?")
            lines.append(f"    {col:30s} {non_null:5d} obs  {first_str} — {last_str}  "
                         f"(lag={lag}d)")
        return "\n".join(lines)


def build_panel(force: bool = False) -> MacroPanel:
    """Download all data and build the MacroPanel.

    Args:
        force: If True, re-download even if cache is fresh.
    """
    logger.info("Building macro panel (force=%s)...", force)

    # Download from all sources
    all_series: dict[str, pd.Series] = {}

    ssb = download_all_ssb(force=force)
    all_series.update(ssb)

    nb = download_all_norges_bank(force=force)
    all_series.update(nb)

    fred = download_all_fred(force=force)
    all_series.update(fred)

    if not all_series:
        logger.error("No series downloaded. Check API keys and network.")
        # Return empty panel
        return MacroPanel(
            data=pd.DataFrame(),
            metadata={},
            publication_lags=load_publication_lags(),
            first_available={},
            last_updated=datetime.now(),
        )

    # Combine into single DataFrame aligned on monthly dates
    data = pd.DataFrame(all_series)
    data.index.name = "date"
    data = data.sort_index()

    # Forward-fill within each series (last known value, never backfill)
    data = data.ffill()

    pub_lags = load_publication_lags()
    first_avail = {
        col: data[col].first_valid_index()
        for col in data.columns
        if data[col].first_valid_index() is not None
    }

    # Build metadata dict
    meta: dict[str, Any] = {}
    for name, cfg in {**SSB_SERIES_CONFIG, **FRED_SERIES_CONFIG, **NORGES_BANK_CONFIG}.items():
        if name in data.columns:
            meta[name] = {"description": cfg.get("description", ""), "source": _source_of(name)}

    panel = MacroPanel(
        data=data,
        metadata=meta,
        publication_lags=pub_lags,
        first_available=first_avail,
        last_updated=datetime.now(),
    )

    # Save to parquet
    save_panel(panel)
    logger.info("Panel built: %d variables, %d months", len(data.columns), len(data))
    return panel


def _source_of(name: str) -> str:
    if name in SSB_SERIES_CONFIG:
        return "SSB"
    if name in NORGES_BANK_CONFIG:
        return "Norges Bank"
    if name in FRED_SERIES_CONFIG:
        return "FRED"
    return "unknown"


def save_panel(panel: MacroPanel) -> Path:
    """Save the panel to parquet and metadata to JSON."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = PROCESSED_DIR / "macro_panel.parquet"
    panel.data.to_parquet(parquet_path)

    meta_out = {
        "metadata": panel.metadata,
        "publication_lags": panel.publication_lags,
        "first_available": {k: v.isoformat() for k, v in panel.first_available.items()},
        "last_updated": panel.last_updated.isoformat(),
        "columns": list(panel.data.columns),
    }
    (PROCESSED_DIR / "panel_meta.json").write_text(json.dumps(meta_out, indent=2))
    logger.info("Panel saved to %s", parquet_path)
    return parquet_path


def load_panel() -> MacroPanel:
    """Load a previously saved MacroPanel from disk."""
    parquet_path = PROCESSED_DIR / "macro_panel.parquet"
    meta_path = PROCESSED_DIR / "panel_meta.json"

    if not parquet_path.exists():
        raise FileNotFoundError(
            f"No panel found at {parquet_path}. Run `python src/prepare.py` first."
        )

    data = pd.read_parquet(parquet_path)
    data.index.name = "date"
    meta_raw = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    first_avail: dict[str, pd.Timestamp] = {}
    for k, v in meta_raw.get("first_available", {}).items():
        first_avail[k] = pd.Timestamp(v)

    return MacroPanel(
        data=data,
        metadata=meta_raw.get("metadata", {}),
        publication_lags=meta_raw.get("publication_lags", load_publication_lags()),
        first_available=first_avail,
        last_updated=datetime.fromisoformat(
            meta_raw.get("last_updated", datetime.now().isoformat())
        ),
    )


# ---------------------------------------------------------------------------
# Evaluation protocol
# ---------------------------------------------------------------------------


@dataclass
class ForecastOrigin:
    """A single forecast evaluation point."""

    origin_date: date
    available_data: pd.DataFrame
    actuals: dict[str, pd.Series]  # variable → Series(index=horizon, value=actual)


def build_validation_origins(
    panel: MacroPanel,
    start: str = "2006-01",
    end: str = "2015-12",
    step_months: int = 1,
    horizons: list[int] | None = None,
) -> list[ForecastOrigin]:
    """Generate rolling forecast origins for the validation era.

    Each origin is an end-of-month date in [start, end]. For each origin,
    we store the data available at that date and the actual future values
    at each forecast horizon.
    """
    if horizons is None:
        horizons = HORIZONS
    return _build_origins(panel, start, end, step_months, horizons)


def build_test_origins(
    panel: MacroPanel,
    start: str = "2016-01",
    end: str | None = None,
    step_months: int = 1,
    horizons: list[int] | None = None,
) -> list[ForecastOrigin]:
    """Generate rolling forecast origins for the test era.

    FROZEN — no search or tuning should use these origins.
    """
    if horizons is None:
        horizons = HORIZONS
    if end is None:
        # Use latest date in panel minus max horizon
        last = panel.data.index[-1]
        end_dt = last - pd.DateOffset(months=max(horizons))
        end = end_dt.strftime("%Y-%m")
    return _build_origins(panel, start, end, step_months, horizons)


def _build_origins(
    panel: MacroPanel,
    start: str,
    end: str,
    step_months: int,
    horizons: list[int],
) -> list[ForecastOrigin]:
    """Internal: build a list of ForecastOrigins."""
    start_date = pd.Timestamp(start) + pd.offsets.MonthEnd(0)
    end_date = pd.Timestamp(end) + pd.offsets.MonthEnd(0)
    target_vars = panel.targets()

    # Use date_range to guarantee month-end dates (DateOffset can drift)
    all_months = pd.date_range(start=start_date, end=end_date, freq="ME")
    origin_months = all_months[::step_months]

    origins: list[ForecastOrigin] = []
    for current in origin_months:
        origin_date = current.date()
        available_data = panel.available_at(origin_date)

        # Collect actual future values for each target × horizon
        actuals: dict[str, pd.Series] = {}
        for var in target_vars:
            if var not in panel.data.columns:
                continue
            horizon_vals: dict[int, float] = {}
            for h in horizons:
                target_date = current + pd.DateOffset(months=h)
                target_date = target_date + pd.offsets.MonthEnd(0)
                if target_date in panel.data.index:
                    val = panel.data.loc[target_date, var]
                    if pd.notna(val):
                        horizon_vals[h] = float(val)
            if horizon_vals:
                actuals[var] = pd.Series(horizon_vals, dtype=float)

        origins.append(ForecastOrigin(
            origin_date=origin_date,
            available_data=available_data,
            actuals=actuals,
        ))

    logger.info("Built %d forecast origins from %s to %s", len(origins), start, end)
    return origins


def evaluate_forecasts(
    forecasts: dict[str, pd.DataFrame],
    origins: list[ForecastOrigin],
    horizons: list[int] | None = None,
) -> dict[str, dict[int, dict[str, float]]]:
    """Compute all evaluation metrics.

    Args:
        forecasts: {variable: DataFrame(index=origin_dates, columns=horizons)}.
            Each cell is a point forecast.
        origins: List of ForecastOrigin objects with actuals.
        horizons: Horizons to evaluate (default: HORIZONS).

    Returns:
        Nested dict: results[variable][horizon] = {"rmse": ..., "mae": ..., ...}
    """
    if horizons is None:
        horizons = HORIZONS

    results: dict[str, dict[int, dict[str, float]]] = {}

    for var, fc_df in forecasts.items():
        results[var] = {}
        for h in horizons:
            if h not in fc_df.columns:
                continue
            actual_list: list[float] = []
            pred_list: list[float] = []

            for origin in origins:
                od = origin.origin_date
                if (var in origin.actuals
                        and h in origin.actuals[var].index
                        and od in fc_df.index):
                    a = origin.actuals[var][h]
                    p = fc_df.loc[od, h]
                    if pd.notna(a) and pd.notna(p):
                        actual_list.append(float(a))
                        pred_list.append(float(p))

            if not actual_list:
                continue

            a_arr = np.array(actual_list)
            p_arr = np.array(pred_list)

            # Naive forecast error (random walk: predict last known value)
            # For h-step ahead: naive error = y_{t+h} - y_t
            naive_errors = np.diff(a_arr) if len(a_arr) > 1 else np.array([1.0])

            results[var][h] = {
                "rmse": rmse(a_arr, p_arr),
                "mae": mae(a_arr, p_arr),
                "mase": mase(a_arr, p_arr, naive_errors),
                "n_origins": len(actual_list),
            }

    return results


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Root Mean Squared Error."""
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Error."""
    return float(np.mean(np.abs(actual - predicted)))


def mase(actual: np.ndarray, predicted: np.ndarray, naive_errors: np.ndarray) -> float:
    """Mean Absolute Scaled Error.

    Args:
        actual: Array of actual values.
        predicted: Array of predicted values.
        naive_errors: Array of naive forecast errors (for scaling).
    """
    model_mae = np.mean(np.abs(actual - predicted))
    naive_mae = np.mean(np.abs(naive_errors))
    if naive_mae == 0:
        return np.inf
    return float(model_mae / naive_mae)


def pinball_loss(
    actual: np.ndarray,
    quantiles: np.ndarray,
    quantile_levels: np.ndarray,
) -> float:
    """Weighted quantile loss (pinball loss) for probabilistic forecasts.

    Args:
        actual: Shape (n,) — actual values.
        quantiles: Shape (n, q) — predicted quantiles for each observation.
        quantile_levels: Shape (q,) — quantile levels, e.g. [0.1, 0.25, 0.5, 0.75, 0.9].

    Returns:
        Average pinball loss across all observations and quantile levels.
    """
    actual_2d = actual[:, np.newaxis]  # (n, 1)
    errors = actual_2d - quantiles  # (n, q)
    loss = np.where(
        errors >= 0,
        quantile_levels * errors,
        (quantile_levels - 1) * errors,
    )
    return float(np.mean(loss))


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find the first matching column name (case-insensitive).

    Handles SDMX-CSV columns like 'TIME_PERIOD:Time Period' by also
    checking the prefix before the colon.
    """
    df_cols_lower = {c.lower(): c for c in df.columns}
    # Also index by prefix before ':'  (e.g. "TIME_PERIOD:Time Period" → "time_period")
    prefix_map = {c.split(":")[0].lower(): c for c in df.columns if ":" in c}
    for cand in candidates:
        cand_lower = cand.lower()
        if cand_lower in df_cols_lower:
            return df_cols_lower[cand_lower]
        if cand_lower in prefix_map:
            return prefix_map[cand_lower]
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _verify_realtime(panel: MacroPanel, origin_str: str) -> None:
    """Verify pseudo-real-time discipline for a given forecast origin."""
    origin = date.fromisoformat(origin_str)
    available = panel.available_at(origin)

    print(f"\n{'=' * 70}")
    print(f"Pseudo-real-time check at forecast origin: {origin}")
    print(f"{'=' * 70}\n")

    for col in available.columns:
        last_obs = available[col].last_valid_index()
        lag = panel.publication_lags.get(col, "?")
        if last_obs is not None:
            days_before = (pd.Timestamp(origin) - last_obs).days
            print(f"  {col:30s}  last obs: {last_obs.date()}  "
                  f"(lag={lag}d, {days_before}d before origin)")
        else:
            print(f"  {col:30s}  no data available")

    # Check for any future leakage
    print(f"\n{'- ' * 35}")
    print("Leakage check:")
    has_leakage = False
    for col in available.columns:
        last_obs = available[col].last_valid_index()
        if last_obs is not None:
            lag = panel.publication_lags.get(col, 30)
            pub_date = last_obs + pd.Timedelta(days=lag)
            if pub_date > pd.Timestamp(origin):
                print(f"  WARNING: {col} — last obs {last_obs.date()} would be published "
                      f"{pub_date.date()}, AFTER origin {origin}")
                has_leakage = True

    if not has_leakage:
        print("  No leakage detected.")
    print()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Data pipeline for autoresearch-macro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--download-only", action="store_true",
        help="Download data without building the panel",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-download even if cache is fresh",
    )
    parser.add_argument(
        "--info", action="store_true",
        help="Show summary of existing panel",
    )
    parser.add_argument(
        "--verify-realtime", type=str, metavar="DATE",
        help="Verify pseudo-real-time discipline at DATE (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.info:
        panel = load_panel()
        print(panel.summary())
        return

    if args.verify_realtime:
        panel = load_panel()
        _verify_realtime(panel, args.verify_realtime)
        return

    if args.download_only:
        download_all_ssb(force=args.force)
        download_all_norges_bank(force=args.force)
        download_all_fred(force=args.force)
        print("Download complete.")
        return

    # Full pipeline: download + build panel
    panel = build_panel(force=args.force)
    print(panel.summary())


if __name__ == "__main__":
    main()
