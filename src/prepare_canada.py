"""Data pipeline for Canada.

Downloads Canadian and global macro data from Statistics Canada,
the Bank of Canada, and FRED. Produces a MacroPanel equivalent to Norway's.

Statistics Canada uses CSV table downloads (not json-stat2).
Bank of Canada uses the Valet JSON API.

Usage:
    python src/prepare_canada.py              # Download and build panel
    python src/prepare_canada.py --info       # Show panel summary
    python src/prepare_canada.py --force      # Force re-download
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

from prepare import (
    CACHE_MAX_AGE_DAYS,
    MacroPanel,
    daily_to_monthly,
    download_all_fred,
    download_fred_series,
    ffill_covariates_only,
    warn_if_targets_stale,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(PROJECT_ROOT / "data")))
RAW_STATCAN_DIR = DATA_DIR / "raw" / "statcan"
RAW_BOC_DIR = DATA_DIR / "raw" / "bank_of_canada"
PROCESSED_DIR = DATA_DIR / "processed" / "canada"
METADATA_PATH = DATA_DIR / "metadata_canada.json"
CONFIGS_DIR = PROJECT_ROOT / "configs"

STATCAN_WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"

# ---------------------------------------------------------------------------
# Statistics Canada series configuration
# ---------------------------------------------------------------------------

STATCAN_SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "cpi": {
        "product_id": "18100006",
        "description": "CPI, all-items, SA (2002=100)",
        "filters": {
            "GEO": "Canada",
            "Products and product groups": "All-items",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
        "transform": "yoy_pct",  # Compute 12-month % change from index
    },
    "industrial_production": {
        "product_id": "36100434",
        "description": "Monthly GDP at basic prices, all industries (2017=100)",
        "filters": {
            "GEO": "Canada",
            "North American Industry Classification System (NAICS)": "All industries [T001]",
            "Seasonal adjustment": "Seasonally adjusted at annual rates",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
    },
    "retail_sales": {
        "product_id": "20100008",
        "description": "Retail trade, SA, current prices (CAD thousands)",
        "filters": {
            "GEO": "Canada",
            "North American Industry Classification System (NAICS)": "Retail trade [44-45]",
            "Adjustments": "Seasonally adjusted",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
        # Note: table 20100008 covers 1991-2022 (terminated).
        # Extended with table 20100067 current-price series for 2023+.
        "extend_with": {
            "product_id": "20100067",
            "filters": {
                "GEO": "Canada",
                "North American Industry Classification System (NAICS)": "Retail trade [44-45]",
                "Sales, price and volume": "Retail sales in current prices",
            },
            "value_column": "VALUE",
            "unit_conversion": 1000,  # 20100008 is thousands, 20100067 is millions
        },
    },
    "unemployment": {
        "product_id": "14100287",
        "description": "Unemployment rate, SA, 15+",
        "filters": {
            "GEO": "Canada",
            "Labour force characteristics": "Unemployment rate",
            "Gender": "Total - Gender",
            "Age group": "15 years and over",
            "Data type": "Seasonally adjusted",
            "Statistics": "Estimate",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
    },
    "house_prices": {
        "product_id": "18100205",
        "description": "New housing price index (NHPI), total, Canada",
        "filters": {
            "GEO": "Canada",
            "New housing price indexes": "Total (house and land)",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
    },
    "credit": {
        "product_id": "10100118",
        "description": "Household credit, SA (CAD millions)",
        "filters": {
            "GEO": "Canada",
            "Type of credit": "Household credit",
            "Seasonal adjustment": "Seasonally adjusted",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
    },
    "exports": {
        "product_id": "12100011",
        "description": "Merchandise exports, total, SA, customs basis",
        "filters": {
            "GEO": "Canada",
            "Trade": "Export",
            "Basis": "Customs",
            "Seasonal adjustment": "Seasonally adjusted",
            "Principal trading partners": "All countries",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
    },
    "imports": {
        "product_id": "12100011",
        "description": "Merchandise imports, total, SA, customs basis",
        "filters": {
            "GEO": "Canada",
            "Trade": "Import",
            "Basis": "Customs",
            "Seasonal adjustment": "Seasonally adjusted",
            "Principal trading partners": "All countries",
        },
        "value_column": "VALUE",
        "frequency": "monthly",
    },
}


# ---------------------------------------------------------------------------
# Bank of Canada configuration
# ---------------------------------------------------------------------------

BOC_VALET_BASE = "https://www.bankofcanada.ca/valet"

BOC_CONFIG: dict[str, dict[str, Any]] = {
    "policy_rate": {
        "series_id": "V39079",
        "description": "Bank of Canada overnight target rate",
        "frequency": "daily",
        "ffill": True,  # Rate only changes on decision dates
    },
    "fx_usd": {
        "series_id": "FXUSDCAD",
        "description": "CAD/USD exchange rate",
        "frequency": "daily",
        # BoC series starts ~2017. Splice with FRED DEXCAUS for pre-2017.
        "fred_backfill": "DEXCAUS",
    },
    "fx_eur": {
        "series_id": "FXEURCAD",
        "description": "CAD/EUR exchange rate",
        "frequency": "daily",
        # BoC series starts ~2017. Splice with FRED DEXCAUS * 1/DEXUSEU for pre-2017.
        "fred_backfill": "DEXCAUS_EUR",  # Synthetic: computed from DEXCAUS and DEXUSEU
    },
}

# Additional FRED series for Canada (partner-area activity)
CANADA_EXTRA_FRED: dict[str, dict[str, Any]] = {
    "partner_activity": {
        "series_id": "INDPRO",
        "description": "US Industrial Production Index",
        "frequency": "monthly",
    },
}


# ---------------------------------------------------------------------------
# Statistics Canada download functions
# ---------------------------------------------------------------------------


def download_statcan_table(product_id: str) -> pd.DataFrame | None:
    """Download a full Statistics Canada table as CSV.

    Uses the WDS REST API to get the download URL, then fetches the ZIP.
    """
    url = f"{STATCAN_WDS_BASE}/getFullTableDownloadCSV/{product_id}/en"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if result.get("status") != "SUCCESS":
            logger.error("StatCan WDS error for %s: %s", product_id, result)
            return None

        csv_url = result["object"]
        logger.info("Downloading StatCan table %s from %s", product_id, csv_url)

        # Download the ZIP file
        zip_resp = requests.get(csv_url, timeout=120)
        zip_resp.raise_for_status()

        # Extract CSV from ZIP
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv") and "MetaData" not in n]
            if not csv_names:
                logger.error("No data CSV found in ZIP for table %s", product_id)
                return None
            with zf.open(csv_names[0]) as csv_file:
                df = pd.read_csv(csv_file, low_memory=False)

        # Cache raw CSV
        cache_dir = RAW_STATCAN_DIR / product_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_dir / "raw.parquet", index=False)

        logger.info("StatCan table %s: %d rows, %d columns", product_id, len(df), len(df.columns))
        return df

    except Exception as e:
        logger.error("Failed to download StatCan table %s: %s", product_id, e)
        return None


def parse_statcan_series(df: pd.DataFrame, config: dict[str, Any]) -> pd.Series | None:
    """Filter a StatCan table DataFrame to extract a single time series."""
    filtered = df.copy()

    for col, value in config.get("filters", {}).items():
        if col in filtered.columns:
            filtered = filtered[filtered[col].str.strip() == value]
        else:
            # Try partial match on column names (StatCan sometimes adds extra text)
            matches = [c for c in filtered.columns if value.lower() in c.lower() or col.lower() in c.lower()]
            if matches:
                filtered = filtered[filtered[matches[0]].str.strip() == value]
            else:
                logger.warning("Column '%s' not found in table. Available: %s",
                               col, list(filtered.columns)[:10])

    if filtered.empty:
        logger.warning("No data after filtering for %s", config.get("description", "unknown"))
        return None

    # Parse dates
    ref_date_col = "REF_DATE"
    if ref_date_col not in filtered.columns:
        # Try alternative column names
        for alt in ["DATE", "Ref_Date", "ref_date"]:
            if alt in filtered.columns:
                ref_date_col = alt
                break

    val_col = config.get("value_column", "VALUE")

    # Build series
    series = filtered[[ref_date_col, val_col]].copy()
    series[val_col] = pd.to_numeric(series[val_col], errors="coerce")
    series = series.dropna(subset=[val_col])

    # Parse dates to month-end
    dates = pd.to_datetime(series[ref_date_col])
    series.index = dates + pd.offsets.MonthEnd(0)
    series = series[val_col]
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]

    return series


def download_all_statcan(force: bool = False) -> dict[str, pd.Series]:
    """Download all Statistics Canada series."""
    result: dict[str, pd.Series] = {}

    # Group by product_id to avoid downloading the same table twice
    tables: dict[str, pd.DataFrame] = {}

    for name, config in STATCAN_SERIES_CONFIG.items():
        cache_key = f"statcan_{name}"
        if not force and _cache_is_fresh(cache_key):
            cached = _load_cached_series(cache_key)
            if cached is not None:
                result[name] = cached
                continue

        pid = config["product_id"]
        if pid not in tables:
            raw_cache = RAW_STATCAN_DIR / pid / "raw.parquet"
            if not force and raw_cache.exists():
                tables[pid] = pd.read_parquet(raw_cache)
            else:
                df = download_statcan_table(pid)
                if df is not None:
                    tables[pid] = df

        if pid not in tables:
            continue

        series = parse_statcan_series(tables[pid], config)
        if series is None:
            continue

        # Extend with a newer table if configured (for splicing terminated tables)
        if "extend_with" in config:
            ext = config["extend_with"]
            ext_pid = ext["product_id"]
            if ext_pid not in tables:
                raw_cache = RAW_STATCAN_DIR / ext_pid / "raw.parquet"
                if not force and raw_cache.exists():
                    tables[ext_pid] = pd.read_parquet(raw_cache)
                else:
                    ext_df = download_statcan_table(ext_pid)
                    if ext_df is not None:
                        tables[ext_pid] = ext_df
            if ext_pid in tables:
                ext_series = parse_statcan_series(tables[ext_pid], ext)
                if ext_series is not None:
                    # Apply unit conversion if needed
                    conv = ext.get("unit_conversion", 1)
                    if conv != 1:
                        ext_series = ext_series * conv
                    # Keep primary data where it exists, extend with new data
                    ext_only = ext_series[ext_series.index > series.index.max()]
                    if not ext_only.empty:
                        series = pd.concat([series, ext_only])
                        series = series.sort_index()
                        logger.info("Extended %s with %d observations from table %s",
                                    name, len(ext_only), ext_pid)

        # Apply transforms
        if config.get("transform") == "yoy_pct":
            # Compute 12-month percentage change from index
            series = series.pct_change(12) * 100
            series = series.dropna()

        series.name = name
        result[name] = series
        _save_cached_series(cache_key, series)
        logger.info("Parsed StatCan %s: %d observations", name, len(series))

    return result


# ---------------------------------------------------------------------------
# Bank of Canada download functions
# ---------------------------------------------------------------------------


def download_boc_series(name: str, config: dict[str, Any]) -> pd.Series | None:
    """Download a single series from the Bank of Canada Valet API."""
    series_id = config["series_id"]
    url = f"{BOC_VALET_BASE}/observations/{series_id}/json?start_date=1990-01-01&end_date=2030-12-31"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        observations = data.get("observations", [])
        if not observations:
            logger.warning("BoC %s returned no observations", name)
            return None

        dates = []
        values = []
        for obs in observations:
            d = obs.get("d")
            v_dict = obs.get(series_id, {})
            v = v_dict.get("v") if isinstance(v_dict, dict) else None
            if d and v:
                try:
                    dates.append(pd.Timestamp(d))
                    values.append(float(v))
                except (ValueError, TypeError):
                    continue

        if not dates:
            logger.warning("BoC %s: no valid observations", name)
            return None

        series = pd.Series(values, index=pd.DatetimeIndex(dates), name=name, dtype=float)
        series = series.sort_index()

        # Cache raw response
        RAW_BOC_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_BOC_DIR / f"{name}.json").write_text(json.dumps(data, default=str))

        # Forward-fill for policy rate (only changes on decision dates)
        if config.get("ffill"):
            full_idx = pd.date_range(series.index.min(), series.index.max(), freq="D")
            series = series.reindex(full_idx).ffill()

        # Convert daily to monthly
        if config.get("frequency") == "daily":
            series = daily_to_monthly(series)

        logger.info("Downloaded BoC %s: %d observations", name, len(series))
        return series

    except Exception as e:
        logger.error("Failed to download BoC %s: %s", name, e)
        return None


def _get_fred_fx_backfill(backfill_key: str) -> pd.Series | None:
    """Get FRED FX data for backfilling BoC series pre-2017."""
    if backfill_key == "DEXCAUS":
        # USD/CAD daily rate from FRED
        series = download_fred_series("_tmp_dexcaus", {
            "series_id": "DEXCAUS", "frequency": "daily",
            "description": "USD/CAD from FRED",
        })
        return series
    elif backfill_key == "DEXCAUS_EUR":
        # Synthetic EUR/CAD = USD/CAD * EUR/USD
        usd_cad = download_fred_series("_tmp_dexcaus", {
            "series_id": "DEXCAUS", "frequency": "daily",
            "description": "USD/CAD from FRED",
        })
        eur_usd = download_fred_series("_tmp_dexuseu", {
            "series_id": "DEXUSEU", "frequency": "daily",
            "description": "USD/EUR from FRED",
        })
        if usd_cad is not None and eur_usd is not None:
            # DEXCAUS = USD per CAD, DEXUSEU = USD per EUR
            # EUR/CAD = DEXUSEU / DEXCAUS (how many CAD per EUR)
            # But BoC FXEURCAD is CAD per EUR
            aligned = pd.DataFrame({"usd_cad": usd_cad, "usd_eur": eur_usd}).dropna()
            eur_cad = aligned["usd_eur"] / aligned["usd_cad"]
            eur_cad.name = "fx_eur"
            return eur_cad
    return None


def download_all_boc(force: bool = False) -> dict[str, pd.Series]:
    """Download all Bank of Canada series, with FRED backfill for pre-2017."""
    result: dict[str, pd.Series] = {}
    for name, config in BOC_CONFIG.items():
        cache_key = f"boc_{name}"
        if not force and _cache_is_fresh(cache_key):
            cached = _load_cached_series(cache_key)
            if cached is not None:
                result[name] = cached
                continue

        series = download_boc_series(name, config)

        # Backfill with FRED data for pre-2017
        backfill_key = config.get("fred_backfill")
        if backfill_key and series is not None:
            fred_daily = _get_fred_fx_backfill(backfill_key)
            if fred_daily is not None:
                fred_monthly = daily_to_monthly(fred_daily)
                # Keep only FRED data before BoC series starts
                boc_start = series.index.min()
                fred_pre = fred_monthly[fred_monthly.index < boc_start]
                if not fred_pre.empty:
                    series = pd.concat([fred_pre, series]).sort_index()
                    series = series[~series.index.duplicated(keep="last")]
                    logger.info("Backfilled %s with %d FRED observations pre-%s",
                                name, len(fred_pre), boc_start.strftime("%Y-%m"))

        if series is not None:
            series.name = name
            result[name] = series
            _save_cached_series(cache_key, series)
    return result


def download_canada_extra_fred(force: bool = False) -> dict[str, pd.Series]:
    """Download Canada-specific FRED series (e.g., US industrial production)."""
    result: dict[str, pd.Series] = {}
    for name, config in CANADA_EXTRA_FRED.items():
        cache_key = f"fred_{name}"
        if not force and _cache_is_fresh(cache_key):
            cached = _load_cached_series(cache_key)
            if cached is not None:
                result[name] = cached
                continue
        series = download_fred_series(name, config)
        if series is not None:
            result[name] = series
            _save_cached_series(cache_key, series)
    return result


# ---------------------------------------------------------------------------
# Caching (mirrors prepare.py pattern)
# ---------------------------------------------------------------------------


def _load_metadata() -> dict:
    if METADATA_PATH.exists():
        with open(METADATA_PATH) as f:
            return json.load(f)
    return {"last_download": {}}


def _save_metadata(meta: dict) -> None:
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(METADATA_PATH, "w") as f:
        json.dump(meta, f, indent=2, default=str)


def _cache_is_fresh(key: str) -> bool:
    meta = _load_metadata()
    last = meta.get("last_download", {}).get(key)
    if last is None:
        return False
    last_dt = datetime.fromisoformat(last)
    return (datetime.now() - last_dt).days < CACHE_MAX_AGE_DAYS


def _save_cached_series(key: str, series: pd.Series) -> None:
    cache_dir = DATA_DIR / "processed" / "series_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    df = series.to_frame(name=key)
    df.to_parquet(cache_dir / f"{key}.parquet")
    meta = _load_metadata()
    meta.setdefault("last_download", {})[key] = datetime.now().isoformat()
    _save_metadata(meta)


def _load_cached_series(key: str) -> pd.Series | None:
    cache_path = DATA_DIR / "processed" / "series_cache" / f"{key}.parquet"
    if not cache_path.exists():
        return None
    df = pd.read_parquet(cache_path)
    series = df.iloc[:, 0]
    series.name = key.split("_", 1)[-1] if "_" in key else key
    return series


# ---------------------------------------------------------------------------
# Panel construction
# ---------------------------------------------------------------------------


def load_publication_lags_canada() -> dict[str, int]:
    """Load Canada-specific publication lags."""
    lag_file = CONFIGS_DIR / "publication_lags.yml"
    if lag_file.exists():
        with open(lag_file) as f:
            all_lags = yaml.safe_load(f)
        if "canada" in all_lags:
            result = {k: int(v) for k, v in all_lags.items() if not isinstance(v, dict)}
            result.update({k: int(v) for k, v in all_lags["canada"].items()})
            return result
    # Fallback
    return {
        "cpi": 18, "unemployment": 8, "industrial_production": 60,
        "retail_sales": 50, "house_prices": 50, "credit": 50,
        "exports": 40, "imports": 40, "policy_rate": 0,
        "fx_eur": 1, "fx_usd": 1, "brent_crude": 1, "sp500": 1,
        "fed_funds": 1, "us_cpi": 15, "vix": 1, "global_epu": 30,
        "partner_activity": 45,
    }


def build_panel_canada(force: bool = False) -> MacroPanel:
    """Build the Canada macro panel."""
    logger.info("Building Canada panel...")

    all_series: dict[str, pd.Series] = {}
    all_series.update(download_all_statcan(force))
    all_series.update(download_all_boc(force))
    all_series.update(download_all_fred(force))
    all_series.update(download_canada_extra_fred(force))

    if not all_series:
        raise RuntimeError("No series downloaded for Canada")

    # Build DataFrame
    data = pd.DataFrame(all_series)
    data = data.sort_index()
    data = ffill_covariates_only(data)
    data.index.name = "date"
    warn_if_targets_stale(data)

    # Compute first available dates
    first_available = {
        col: data[col].first_valid_index() for col in data.columns
    }

    # Build metadata
    metadata: dict[str, Any] = {}
    for name in STATCAN_SERIES_CONFIG:
        if name in data.columns:
            metadata[name] = {
                "description": STATCAN_SERIES_CONFIG[name]["description"],
                "source": "Statistics Canada",
            }
    for name in BOC_CONFIG:
        if name in data.columns:
            metadata[name] = {
                "description": BOC_CONFIG[name]["description"],
                "source": "Bank of Canada",
            }
    for col in data.columns:
        if col not in metadata:
            metadata[col] = {"description": col, "source": "FRED"}

    pub_lags = load_publication_lags_canada()

    panel = MacroPanel(
        data=data,
        metadata=metadata,
        publication_lags=pub_lags,
        first_available=first_available,
        last_updated=datetime.now(),
    )

    save_panel_canada(panel)
    logger.info("Canada panel built: %d variables, %d months", len(data.columns), len(data))
    return panel


def save_panel_canada(panel: MacroPanel) -> Path:
    """Save the Canada panel to disk."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = PROCESSED_DIR / "macro_panel.parquet"
    panel.data.to_parquet(panel_path)

    meta_path = PROCESSED_DIR / "panel_meta.json"
    meta = {
        "columns": list(panel.data.columns),
        "n_months": len(panel.data),
        "date_range": [
            panel.data.index.min().isoformat() if len(panel.data) > 0 else None,
            panel.data.index.max().isoformat() if len(panel.data) > 0 else None,
        ],
        "publication_lags": panel.publication_lags,
        "first_available": {k: v.isoformat() if v is not None else None
                           for k, v in panel.first_available.items()},
        "last_updated": panel.last_updated.isoformat(),
        "country": "canada",
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return panel_path


def load_panel_canada() -> MacroPanel:
    """Load the Canada panel from disk."""
    panel_path = PROCESSED_DIR / "macro_panel.parquet"
    meta_path = PROCESSED_DIR / "panel_meta.json"

    data = pd.read_parquet(panel_path)
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)
    data.index.name = "date"

    with open(meta_path) as f:
        meta = json.load(f)

    pub_lags = meta.get("publication_lags", load_publication_lags_canada())
    first_available = {}
    for k, v in meta.get("first_available", {}).items():
        first_available[k] = pd.Timestamp(v) if v else None

    return MacroPanel(
        data=data,
        metadata=meta.get("metadata", {}),
        publication_lags=pub_lags,
        first_available=first_available,
        last_updated=datetime.fromisoformat(meta.get("last_updated", "2026-01-01")),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Canada data pipeline")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    parser.add_argument("--info", action="store_true", help="Show panel summary")
    args = parser.parse_args()

    if args.info:
        panel = load_panel_canada()
        print(panel.summary())
        return

    panel = build_panel_canada(force=args.force)
    print(f"Canada panel: {len(panel.data.columns)} variables, "
          f"{len(panel.data)} months")
    targets = panel.targets()
    print(f"Targets: {targets}")
    covariates = panel.covariates()
    print(f"Covariates: {covariates}")


if __name__ == "__main__":
    main()
