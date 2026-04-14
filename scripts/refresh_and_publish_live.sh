#!/bin/bash
# Refresh data, regenerate live forecasts, and publish to MacroLab.
#
# This is the manual end-to-end script you run when you want the
# autoresearch-macro card on the MacroLab homepage to show fresh
# fan-chart forecasts. Steps:
#
#   1. Re-download macro data for all three countries (respects API caches).
#   2. Run src/live_forecast.py to produce per-country JSON in results/live/.
#   3. Aggregate into webapp/_data/live_forecasts.json.
#   4. Render the Quarto webapp and publish to MacroLab via publish_to_macrolab.sh.
#
# Flags:
#   --skip-data    Don't refresh data, reuse cached parquet panels.
#   --skip-models  Don't re-run forecasts, reuse results/live/*.json.
#   --countries    Comma-separated subset (default: all).
#   --origin       Forecast origin date YYYY-MM-DD (default: today UTC).
#   Remaining args are forwarded to publish_to_macrolab.sh.

set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)

SKIP_DATA=0
SKIP_MODELS=0
COUNTRIES="norway,canada,sweden"
ORIGIN=""
PUBLISH_ARGS=()

usage() {
    sed -n '1,/^set -euo pipefail/p' "$0" | sed '$d'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-data) SKIP_DATA=1; shift ;;
        --skip-models) SKIP_MODELS=1; shift ;;
        --countries) COUNTRIES="$2"; shift 2 ;;
        --origin) ORIGIN="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) PUBLISH_ARGS+=("$1"); shift ;;
    esac
done

cd "${PROJECT_ROOT}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
    PYTHON_RUNNER=("${PYTHON_BIN}")
elif [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON_RUNNER=("${PROJECT_ROOT}/.venv/bin/python")
else
    PYTHON_RUNNER=(uv run python)
fi

run() {
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
    "$@"
}

IFS=',' read -ra COUNTRY_ARR <<< "${COUNTRIES}"

# Step 1 — refresh data
if [[ "${SKIP_DATA}" -eq 0 ]]; then
    for country in "${COUNTRY_ARR[@]}"; do
        case "${country}" in
            norway)  run "${PYTHON_RUNNER[@]}" src/prepare.py ;;
            canada)  run "${PYTHON_RUNNER[@]}" src/prepare_canada.py ;;
            sweden)  run "${PYTHON_RUNNER[@]}" src/prepare_sweden.py ;;
            *) echo "Unknown country: ${country}" >&2; exit 1 ;;
        esac
    done
fi

# Step 2 — live forecasts (Chronos-2 quantile + BVAR + ETS)
if [[ "${SKIP_MODELS}" -eq 0 ]]; then
    export HF_HUB_OFFLINE=1
    for country in "${COUNTRY_ARR[@]}"; do
        cmd=("${PYTHON_RUNNER[@]}" src/live_forecast.py --country "${country}")
        if [[ -n "${ORIGIN}" ]]; then
            cmd+=(--origin "${ORIGIN}")
        fi
        run "${cmd[@]}"
    done
fi

# Step 3 — aggregate JSON
run "${PYTHON_RUNNER[@]}" scripts/build_live_forecasts_json.py

# Step 4 — render webapp & publish
run "${SCRIPT_DIR}/publish_to_macrolab.sh" "${PUBLISH_ARGS[@]}"
