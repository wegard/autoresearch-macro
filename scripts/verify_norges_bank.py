"""Diagnostic script to verify Norges Bank SDMX API endpoints.

Tests exchange rate and policy rate endpoints to confirm correct
flow/key combinations for prepare.py.

Usage:
    uv run python scripts/verify_norges_bank.py
"""

from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

NORGES_BANK_API_BASE = "https://data.norges-bank.no/api/data"

# Endpoints to verify
ENDPOINTS = {
    "nok_eur": {
        "flow": "EXR",
        "key": "B.EUR.NOK.SP",
        "description": "NOK/EUR exchange rate (daily)",
    },
    "nok_usd": {
        "flow": "EXR",
        "key": "B.USD.NOK.SP",
        "description": "NOK/USD exchange rate (daily)",
    },
    "policy_rate_v1": {
        "flow": "IR",
        "key": "B..KPRA.R",
        "description": "Policy rate — current key in prepare.py",
    },
    "policy_rate_v2": {
        "flow": "IR",
        "key": "B.KPRA..",
        "description": "Policy rate — alternative 1",
    },
    "policy_rate_v3": {
        "flow": "IR",
        "key": "M.KPRA..",
        "description": "Policy rate — alternative 2 (monthly)",
    },
}


def test_endpoint(name: str, config: dict) -> None:
    """Test a single SDMX endpoint."""
    flow = config["flow"]
    key = config["key"]
    url = f"{NORGES_BANK_API_BASE}/{flow}/{key}"
    params = {
        "format": "sdmx-csv",
        "startPeriod": "2020-01-01",
        "endPeriod": "2025-12-31",
    }

    print(f"\n{'- ' * 40}")
    print(f"Testing: {name}")
    print(f"  URL: {url}")
    print(f"  Description: {config['description']}")

    try:
        resp = requests.get(url, params=params, timeout=30)
        print(f"  Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"  Response: {resp.text[:300]}")
            return

        df = pd.read_csv(StringIO(resp.text))
        print(f"  Columns: {list(df.columns)}")
        print(f"  Rows: {len(df)}")

        # Show first and last few rows
        if len(df) > 0:
            # Identify time and value columns
            time_cols = [c for c in df.columns if "time" in c.lower() or "period" in c.lower()]
            value_cols = [c for c in df.columns if "value" in c.lower() or "obs" in c.lower()]

            if time_cols and value_cols:
                tc, vc = time_cols[0], value_cols[0]
                print(f"  Time column: {tc}")
                print(f"  Value column: {vc}")
                print(f"  First 3 rows:")
                for _, row in df.head(3).iterrows():
                    print(f"    {row[tc]}  ->  {row[vc]}")
                print(f"  Last 3 rows:")
                for _, row in df.tail(3).iterrows():
                    print(f"    {row[tc]}  ->  {row[vc]}")
                print(f"  Date range: {df[tc].min()} to {df[tc].max()}")
            else:
                print(f"  First row: {df.iloc[0].to_dict()}")

    except Exception as e:
        print(f"  ERROR: {e}")


def main() -> None:
    print("Norges Bank SDMX API Verification")
    print(f"API base: {NORGES_BANK_API_BASE}")

    for name, config in ENDPOINTS.items():
        test_endpoint(name, config)

    print(f"\n{'=' * 80}")
    print("VERIFICATION COMPLETE")
    print("Key question: Which policy rate endpoint works and returns sensible data?")


if __name__ == "__main__":
    main()
