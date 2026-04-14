#!/usr/bin/env python3
"""Build a MacroLab publication manifest for autoresearch-macro."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
WEBAPP_DATA_DIR = PROJECT_ROOT / "webapp" / "_data"
FORECAST_ERRORS_PATH = RESULTS_DIR / "forecast_errors.parquet"
LIVE_FORECASTS_PATH = WEBAPP_DATA_DIR / "live_forecasts.json"

DEFAULT_ENTRYPOINT = "/published/autoresearch-macro/index.html"
DEFAULT_LIVE_DATA_URL = "/published/autoresearch-macro/live_forecasts.json"
DEFAULT_HEADLINE = (
    "Agentic search over macro forecasting pipelines across Norway, Canada, and Sweden"
)

SEARCH_STATE_FILES = {
    "norway": "search_state_llm_42.json",
    "canada": "search_state_llm_42.json",
    "sweden": "search_state_llm_fixedgate_42.json",
}

COUNTRY_DISPLAY = {
    "norway": "Norway",
    "canada": "Canada",
    "sweden": "Sweden",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write the manifest JSON to. Defaults to stdout.",
    )
    parser.add_argument(
        "--entrypoint",
        default=DEFAULT_ENTRYPOINT,
        help="Published app entrypoint MacroLab should link to.",
    )
    parser.add_argument(
        "--headline",
        default=DEFAULT_HEADLINE,
        help="Short headline shown in the MacroLab project shell.",
    )
    parser.add_argument(
        "--published-at",
        default=None,
        help="UTC ISO-8601 timestamp. Defaults to now.",
    )
    parser.add_argument(
        "--repo-url",
        default=None,
        help="Optional repository URL to include in the manifest links.",
    )
    parser.add_argument(
        "--paper-url",
        default=None,
        help="Optional paper or manuscript URL to include in the manifest links.",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Mark the artifact as embeddable inside MacroLab.",
    )
    parser.add_argument(
        "--live-data-url",
        default=None,
        help=(
            "URL where MacroLab can fetch the live forecasts JSON. "
            "Defaults to the standard published path if a live_forecasts.json "
            "file is present alongside the webapp data."
        ),
    )
    return parser.parse_args()


def _iso_utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_timestamp(value: str | None) -> str:
    if not value:
        return _iso_utc_now()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    revision = result.stdout.strip()
    return revision or None


def _load_forecast_errors() -> pd.DataFrame | None:
    if not FORECAST_ERRORS_PATH.exists():
        return None
    return pd.read_parquet(
        FORECAST_ERRORS_PATH,
        columns=["country", "model_variant", "origin_date", "is_validation"],
    )


def _format_month_range(start: pd.Timestamp, end: pd.Timestamp) -> str:
    start_label = start.strftime("%Y-%m")
    end_label = end.strftime("%Y-%m")
    if start_label == end_label:
        return start_label
    return f"{start_label} to {end_label}"


def _load_summary_stats() -> list[dict[str, str]]:
    stats: list[dict[str, str]] = []
    df = _load_forecast_errors()

    if df is not None and not df.empty:
        countries = sorted({str(country) for country in df["country"].dropna().unique()})
        methods = sorted({str(method) for method in df["model_variant"].dropna().unique()})

        if countries:
            subtitle = ", ".join(COUNTRY_DISPLAY.get(country, country.title()) for country in countries)
            stats.append(
                {
                    "label": "Countries",
                    "value": str(len(countries)),
                    "subtitle": subtitle,
                }
            )

        validation = df[df["is_validation"].fillna(False)].copy()
        if not validation.empty:
            validation["origin_date"] = pd.to_datetime(validation["origin_date"])
            start = validation["origin_date"].min()
            end = validation["origin_date"].max()
            if pd.notna(start) and pd.notna(end):
                stats.append(
                    {
                        "label": "Validation era",
                        "value": _format_month_range(start, end),
                    }
                )

        if methods:
            stats.append(
                {
                    "label": "Methods compared",
                    "value": str(len(methods)),
                }
            )

    best_score = _load_best_informed_validation_score()
    if best_score is not None:
        stats.append(
            {
                "label": "Best informed val MASE",
                "value": f"{best_score:.3f}",
            }
        )

    return stats


def _load_best_informed_validation_score() -> float | None:
    pipeline_configs_path = WEBAPP_DATA_DIR / "pipeline_configs.json"
    if pipeline_configs_path.exists():
        payload = json.loads(pipeline_configs_path.read_text())
        scores = [
            float(entry["best_score"])
            for entry in payload.values()
            if isinstance(entry, dict) and entry.get("best_score") is not None
        ]
        if scores:
            return min(scores)

    scores: list[float] = []
    for country, filename in SEARCH_STATE_FILES.items():
        path = RESULTS_DIR / country / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        score = payload.get("best_score")
        if score is None:
            continue
        scores.append(float(score))
    if scores:
        return min(scores)
    return None


def _build_links(repo_url: str | None, paper_url: str | None) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if repo_url:
        links.append({"label": "Repository", "href": repo_url})
    if paper_url:
        links.append({"label": "Paper", "href": paper_url})
    return links


def _resolve_live_data_url(explicit: str | None) -> str | None:
    """Pick the live_data_url to advertise in the manifest.

    Order: explicit CLI override → default path if live_forecasts.json exists
    next to the webapp data → None (omit the field).
    """
    if explicit:
        explicit = explicit.strip()
        return explicit or None
    if LIVE_FORECASTS_PATH.exists():
        return DEFAULT_LIVE_DATA_URL
    return None


def _build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "integration_mode": "artifact_site",
        "entrypoint": args.entrypoint,
        "headline": args.headline,
        "published_at": _normalize_timestamp(args.published_at),
        "source_revision": _git_revision(),
        "summary_stats": _load_summary_stats(),
        "links": _build_links(args.repo_url, args.paper_url),
        "embed": args.embed,
    }
    live_data_url = _resolve_live_data_url(args.live_data_url)
    if live_data_url is not None:
        manifest["live_data_url"] = live_data_url
    return manifest


def main() -> int:
    args = _parse_args()
    manifest = _build_manifest(args)
    rendered = json.dumps(manifest, indent=2) + "\n"

    if args.output is None:
        print(rendered, end="")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
