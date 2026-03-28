"""Diagnostic script to verify SSB table IDs and discover correct content codes.

This script queries the SSB API metadata endpoint for each configured table
and prints all available dimensions, codes, and labels. Use the output to
determine the correct content_code values for prepare.py.

Usage:
    uv run python scripts/verify_ssb_tables.py
    uv run python scripts/verify_ssb_tables.py --table 03013
    uv run python scripts/verify_ssb_tables.py --download-sample
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

SSB_API_BASE = "https://data.ssb.no/api/v0/en/table"

# Tables to verify — from prepare.py SSB_SERIES_CONFIG
TABLES_TO_VERIFY: dict[str, dict[str, str]] = {
    "03013": {"purpose": "CPI (consumer price index)", "note": "Spec also mentioned 14700"},
    "14700": {"purpose": "CPI alternative table", "note": "Check if this has 12-month change"},
    "14208": {"purpose": "Industrial production index"},
    "07129": {"purpose": "Retail trade index"},
    "07221": {"purpose": "House price index (quarterly)"},
    "11599": {"purpose": "Credit indicator (C2)"},
    "08799": {"purpose": "External trade (exports AND imports — need separate content codes)"},
    "01598": {"purpose": "Registered unemployment (monthly)"},
    "13967": {"purpose": "LFS unemployment (quarterly alternative)", "note": "Alternative to 01598"},
}


def fetch_table_metadata(table_id: str) -> dict[str, Any] | None:
    """Fetch metadata for a single SSB table."""
    url = f"{SSB_API_BASE}/{table_id}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP error for table {table_id}: {e}")
        return None
    except Exception as e:
        print(f"  Error fetching table {table_id}: {e}")
        return None


def print_table_info(table_id: str, meta: dict[str, Any], info: dict[str, str]) -> None:
    """Print formatted metadata for a table."""
    title = meta.get("title", "Unknown")
    print(f"\n{'=' * 80}")
    print(f"TABLE {table_id}: {title}")
    print(f"Purpose: {info.get('purpose', '?')}")
    if "note" in info:
        print(f"Note: {info['note']}")
    print(f"{'=' * 80}")

    variables = meta.get("variables", [])
    for var in variables:
        code = var.get("code", "?")
        text = var.get("text", "?")
        values = var.get("values", [])
        value_texts = var.get("valueTexts", [])

        print(f"\n  Dimension: {code} ({text})")
        print(f"  Values ({len(values)}):")

        # Show all values for non-time dimensions, first/last 5 for time
        is_time = code.lower() in ("tid", "time", "måned", "kvartal", "år")
        if is_time and len(values) > 10:
            for v, t in zip(values[:3], value_texts[:3]):
                print(f"    {v:20s} -> {t}")
            print(f"    ... ({len(values) - 6} more) ...")
            for v, t in zip(values[-3:], value_texts[-3:]):
                print(f"    {v:20s} -> {t}")
        else:
            for v, t in zip(values, value_texts):
                print(f"    {v:20s} -> {t}")


def download_sample(table_id: str, meta: dict[str, Any]) -> None:
    """Download a small sample from the table to verify data format."""
    url = f"{SSB_API_BASE}/{table_id}"
    variables = meta.get("variables", [])

    query_dims: list[dict] = []
    for var in variables:
        code = var["code"]
        values = var.get("values", [])

        if code.lower() in ("tid", "time", "måned", "kvartal", "år"):
            # Take last 3 time periods
            query_dims.append({
                "code": code,
                "selection": {"filter": "item", "values": values[-3:]},
            })
        elif values:
            # Take first value
            query_dims.append({
                "code": code,
                "selection": {"filter": "item", "values": [values[0]]},
            })

    query = {"query": query_dims, "response": {"format": "json-stat2"}}

    try:
        resp = requests.post(url, json=query, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        print(f"\n  Sample response (first value of each dim, last 3 time periods):")
        print(f"  Dimensions: {data.get('id', [])}")
        print(f"  Sizes: {data.get('size', [])}")
        values = data.get("value", [])
        print(f"  Values: {values}")

        # Show time labels
        for dim_id in data.get("id", []):
            dim = data.get("dimension", {}).get(dim_id, {})
            cat = dim.get("category", {})
            labels = cat.get("label", {})
            if labels:
                print(f"  {dim_id} labels: {dict(list(labels.items())[:5])}")
    except Exception as e:
        print(f"  Sample download failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SSB table IDs and content codes")
    parser.add_argument("--table", type=str, help="Check only this table ID")
    parser.add_argument("--download-sample", action="store_true",
                        help="Also download a small data sample from each table")
    args = parser.parse_args()

    tables = TABLES_TO_VERIFY
    if args.table:
        if args.table in tables:
            tables = {args.table: tables[args.table]}
        else:
            tables = {args.table: {"purpose": "user-specified"}}

    print("SSB Table Verification")
    print(f"API base: {SSB_API_BASE}")
    print(f"Tables to check: {len(tables)}")

    for table_id, info in tables.items():
        meta = fetch_table_metadata(table_id)
        if meta is None:
            print(f"\n  FAILED to fetch table {table_id}")
            continue

        print_table_info(table_id, meta, info)

        if args.download_sample:
            download_sample(table_id, meta)

    print(f"\n{'=' * 80}")
    print("VERIFICATION COMPLETE")
    print("Use the output above to determine correct content_code values for prepare.py.")
    print("Key questions to resolve:")
    print("  1. CPI: Which table (03013 vs 14700) and which ContentsCode?")
    print("  2. Trade (08799): Which ContentsCode for exports vs imports?")
    print("  3. Unemployment: 01598 (registered) vs 13967 (LFS)?")
    print("  4. All tables: Is the first value of each dimension the right aggregate?")


if __name__ == "__main__":
    main()
