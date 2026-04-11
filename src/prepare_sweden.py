"""Data pipeline for Sweden.

Downloads Swedish and global macro data from SCB (Statistics Sweden),
the Riksbank, and FRED. Produces a MacroPanel equivalent to Norway's.

The SCB PxWeb API uses json-stat2 format — identical to SSB Norway,
so we reuse the existing parser from prepare.py.

Usage:
    python src/prepare_sweden.py              # Download and build panel
    python src/prepare_sweden.py --info       # Show panel summary
    python src/prepare_sweden.py --force      # Force re-download
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

from prepare import (
    CACHE_MAX_AGE_DAYS,
    MacroPanel,
    _parse_jsonstat2,
    daily_to_monthly,
    download_all_fred,
    quarterly_to_monthly,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(PROJECT_ROOT / "data")))
RAW_SCB_DIR = DATA_DIR / "raw" / "scb"
RAW_RIKSBANK_DIR = DATA_DIR / "raw" / "riksbank"
PROCESSED_DIR = DATA_DIR / "processed" / "sweden"
METADATA_PATH = DATA_DIR / "metadata_sweden.json"
CONFIGS_DIR = PROJECT_ROOT / "configs"

SCB_API_BASE = "https://api.scb.se/OV0104/v1/doris/en/ssd"

# Series excluded from the Sweden panel because the SCB table we know about
# does not publish a long enough history. Documented in
# metadata/sweden_target_notes.md. Revisit if a longer-history table is found.
DROPPED_VARIABLES: list[str] = ["retail_sales"]

# ---------------------------------------------------------------------------
# SCB series configuration
# ---------------------------------------------------------------------------

SCB_SERIES_CONFIG: dict[str, dict[str, Any]] = {
    "cpi": {
        "path": "PR/PR0101/PR0101A/KPItotM",
        "description": "CPI annual changes (%)",
        "selections": {"ContentsCode": ["000004VV"]},  # Annual changes
        "frequency": "monthly",
    },
    "industrial_production": {
        "path": "NV/NV0402/NV0402A/IPI2010KedjM",
        "description": "Industrial production index, SA (2015=100)",
        "selections": {
            "ContentsCode": ["NV0402AL"],  # Calendar adjusted + seasonally adjusted
            "SNI2007": ["B+C"],  # Mining + Manufacturing
        },
        "frequency": "monthly",
    },
    "retail_sales": {
        "path": "HA/HA0101/HA0101B/Detoms07N",
        "description": "Retail sales volume index, SA",
        "selections": {
            "ContentsCode": ["000006VX"],  # SA, working-day adjusted, constant prices
            "SNI2007": ["47"],  # Total retail trade (NACE 47)
        },
        "frequency": "monthly",
    },
    "unemployment": {
        "path": "AM/AM0401/AM0401A/AKURLBefM",
        "description": "Unemployment rate (LFS, 15-74), SA",
        "selections": {
            "Arbetskraftstillh": ["ALÖSP"],  # Unemployment rate (%)
            "TypData": ["SR_DATA"],  # Seasonally adjusted
            "Kon": ["1+2"],  # Both sexes
            "Alder": ["tot15-74"],  # Total 15-74
            "ContentsCode": ["000007L9"],
        },
        "frequency": "monthly",
    },
    "house_prices": {
        "path": "BO/BO0501/BO0501A/FastpiPSRegKv",
        "description": "House price index, one/two dwelling buildings (quarterly)",
        "selections": {
            "Region": ["00"],  # Whole country
            "ContentsCode": ["BO0501K2"],  # Index
        },
        "frequency": "quarterly",
    },
    "credit": {
        "path": "FM/FM5001/FM5001A/FM5001SDDSMFI",
        "description": "MFI lending to households (SEK million)",
        "selections": {
            "Institut": ["MFI"],
            "KontopostMotsektor": ["5AM2C.1E.N31.V.A"],  # Loans to households
            "ContentsCode": ["0000000I"],  # SEK millions
        },
        "frequency": "monthly",
    },
    "exports": {
        "path": "HA/HA0201/HA0201A/ImportExportSnabbM",
        "description": "Total merchandise exports (SEK million)",
        "selections": {
            "ImportExport": ["ETOT"],  # Total exports
            "ContentsCode": ["HA0201A2"],
        },
        "frequency": "monthly",
    },
    "imports": {
        "path": "HA/HA0201/HA0201A/ImportExportSnabbM",
        "description": "Total merchandise imports (SEK million)",
        "selections": {
            "ImportExport": ["ITOT"],  # Total imports
            "ContentsCode": ["HA0201A2"],
        },
        "frequency": "monthly",
    },
}


# ---------------------------------------------------------------------------
# Riksbank configuration
# ---------------------------------------------------------------------------

RIKSBANK_API_BASE = "https://api.riksbank.se/swea/v1"

RIKSBANK_CONFIG: dict[str, dict[str, Any]] = {
    "policy_rate": {
        "series_id": "SECBREPOEFF",
        "description": "Riksbank repo rate",
        "frequency": "daily",
    },
    "fx_eur": {
        "series_id": "SEKEURPMI",
        "description": "SEK/EUR exchange rate",
        "frequency": "daily",
    },
    "fx_usd": {
        "series_id": "SEKUSDPMI",
        "description": "SEK/USD exchange rate",
        "frequency": "daily",
    },
}


# ---------------------------------------------------------------------------
# Download functions
# ---------------------------------------------------------------------------


def download_scb_series(name: str, config: dict[str, Any]) -> pd.Series | None:
    """Download a single series from the SCB PxWeb v1 API."""
    url = f"{SCB_API_BASE}/{config['path']}"
    try:
        # Step 1: GET metadata to discover dimensions
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        meta = resp.json()

        # Step 2: Build POST query
        query_items: list[dict] = []
        for var in meta["variables"]:
            code = var["code"]
            if var.get("time", False):
                query_items.append({
                    "code": code,
                    "selection": {"filter": "all", "values": ["*"]},
                })
            elif code in config.get("selections", {}):
                query_items.append({
                    "code": code,
                    "selection": {
                        "filter": "item",
                        "values": config["selections"][code],
                    },
                })
            else:
                # Default: select first value
                query_items.append({
                    "code": code,
                    "selection": {
                        "filter": "item",
                        "values": [var["values"][0]],
                    },
                })

        body = {
            "query": query_items,
            "response": {"format": "json-stat2"},
        }

        # Step 3: POST for data
        resp = requests.post(url, json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # Step 4: Parse json-stat2 (same format as SSB)
        series = _parse_jsonstat2(data)
        series.name = name

        # Cache raw response
        cache_dir = RAW_SCB_DIR / name
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "response.json").write_text(json.dumps(data))

        # Handle frequency
        if config.get("frequency") == "quarterly":
            series = quarterly_to_monthly(series)

        logger.info("Downloaded SCB %s: %d observations", name, len(series))
        return series

    except Exception as e:
        logger.error("Failed to download SCB %s: %s", name, e)
        return None


def download_all_scb(force: bool = False) -> dict[str, pd.Series]:
    """Download all SCB series."""
    result: dict[str, pd.Series] = {}
    for name, config in SCB_SERIES_CONFIG.items():
        cache_key = f"scb_{name}"
        if not force and _cache_is_fresh(cache_key):
            cached = _load_cached_series(cache_key)
            if cached is not None:
                result[name] = cached
                continue
        series = download_scb_series(name, config)
        if series is not None:
            result[name] = series
            _save_cached_series(cache_key, series)
    return result


def download_riksbank_series(name: str, config: dict[str, Any]) -> pd.Series | None:
    """Download a single series from the Riksbank API."""
    series_id = config["series_id"]
    url = f"{RIKSBANK_API_BASE}/Observations/{series_id}/1990-01-01/2030-12-31"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            logger.warning("Riksbank %s returned empty data", name)
            return None

        dates = [pd.Timestamp(d["date"]) for d in data]
        values = [d["value"] for d in data]
        series = pd.Series(values, index=pd.DatetimeIndex(dates), name=name, dtype=float)
        series = series.sort_index()

        # Cache raw response
        RAW_RIKSBANK_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_RIKSBANK_DIR / f"{name}.json").write_text(json.dumps(data))

        # Convert daily to monthly
        if config.get("frequency") == "daily":
            series = daily_to_monthly(series)

        logger.info("Downloaded Riksbank %s: %d observations", name, len(series))
        return series

    except Exception as e:
        logger.error("Failed to download Riksbank %s: %s", name, e)
        return None


def download_all_riksbank(force: bool = False) -> dict[str, pd.Series]:
    """Download all Riksbank series."""
    result: dict[str, pd.Series] = {}
    for name, config in RIKSBANK_CONFIG.items():
        cache_key = f"riksbank_{name}"
        if not force and _cache_is_fresh(cache_key):
            cached = _load_cached_series(cache_key)
            if cached is not None:
                result[name] = cached
                continue
        series = download_riksbank_series(name, config)
        if series is not None:
            result[name] = series
            _save_cached_series(cache_key, series)
    return result


# ---------------------------------------------------------------------------
# Caching (mirrors prepare.py pattern, with Sweden-specific paths)
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


def load_publication_lags_sweden() -> dict[str, int]:
    """Load Sweden-specific publication lags."""
    lag_file = CONFIGS_DIR / "publication_lags.yml"
    if lag_file.exists():
        with open(lag_file) as f:
            all_lags = yaml.safe_load(f)
        if "sweden" in all_lags:
            result = {k: int(v) for k, v in all_lags.items() if not isinstance(v, dict)}
            result.update({k: int(v) for k, v in all_lags["sweden"].items()})
            return result
    # Fallback
    return {
        "cpi": 12, "unemployment": 22, "industrial_production": 40,
        "retail_sales": 28, "house_prices": 45, "credit": 30,
        "exports": 35, "imports": 35, "policy_rate": 0,
        "fx_eur": 1, "fx_usd": 1, "brent_crude": 1, "sp500": 1,
        "fed_funds": 1, "us_cpi": 15, "vix": 1, "global_epu": 30,
        "euro_area_gdp": 90,
    }


def build_panel_sweden(force: bool = False) -> MacroPanel:
    """Build the Sweden macro panel."""
    logger.info("Building Sweden panel...")

    all_series: dict[str, pd.Series] = {}
    all_series.update(download_all_scb(force))
    all_series.update(download_all_riksbank(force))
    all_series.update(download_all_fred(force))

    if not all_series:
        raise RuntimeError("No series downloaded for Sweden")

    # Build DataFrame
    data = pd.DataFrame(all_series)
    data = data.sort_index()
    data = data.ffill()
    data.index.name = "date"

    # Drop variables with insufficient validation-era coverage
    for col in DROPPED_VARIABLES:
        if col in data.columns:
            logger.info("Dropping %s from Sweden panel (see DROPPED_VARIABLES)", col)
            data = data.drop(columns=[col])

    # Compute first available dates
    first_available = {
        col: data[col].first_valid_index() for col in data.columns
    }

    # Build metadata
    metadata: dict[str, Any] = {}
    for name in SCB_SERIES_CONFIG:
        if name in data.columns:
            metadata[name] = {
                "description": SCB_SERIES_CONFIG[name]["description"],
                "source": "SCB",
            }
    for name in RIKSBANK_CONFIG:
        if name in data.columns:
            metadata[name] = {
                "description": RIKSBANK_CONFIG[name]["description"],
                "source": "Riksbank",
            }
    # FRED series metadata
    for col in data.columns:
        if col not in metadata:
            metadata[col] = {"description": col, "source": "FRED"}

    pub_lags = load_publication_lags_sweden()

    panel = MacroPanel(
        data=data,
        metadata=metadata,
        publication_lags=pub_lags,
        first_available=first_available,
        last_updated=datetime.now(),
    )

    # Save
    save_panel_sweden(panel)
    logger.info("Sweden panel built: %d variables, %d months", len(data.columns), len(data))
    return panel


def save_panel_sweden(panel: MacroPanel) -> Path:
    """Save the Sweden panel to disk."""
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
        "country": "sweden",
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return panel_path


def load_panel_sweden() -> MacroPanel:
    """Load the Sweden panel from disk."""
    panel_path = PROCESSED_DIR / "macro_panel.parquet"
    meta_path = PROCESSED_DIR / "panel_meta.json"

    data = pd.read_parquet(panel_path)
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)
    data.index.name = "date"

    # Defensive: also drop variables here in case the cached panel pre-dates
    # the DROPPED_VARIABLES constant.
    for col in DROPPED_VARIABLES:
        if col in data.columns:
            data = data.drop(columns=[col])

    with open(meta_path) as f:
        meta = json.load(f)

    pub_lags = meta.get("publication_lags", load_publication_lags_sweden())
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

    parser = argparse.ArgumentParser(description="Sweden data pipeline")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    parser.add_argument("--info", action="store_true", help="Show panel summary")
    parser.add_argument("--download-only", action="store_true", help="Download only")
    args = parser.parse_args()

    if args.info:
        panel = load_panel_sweden()
        print(panel.summary())
        return

    panel = build_panel_sweden(force=args.force)

    if not args.download_only:
        print(f"Sweden panel: {len(panel.data.columns)} variables, "
              f"{len(panel.data)} months")
        targets = panel.targets()
        print(f"Targets: {targets}")
        covariates = panel.covariates()
        print(f"Covariates: {covariates}")


if __name__ == "__main__":
    main()
