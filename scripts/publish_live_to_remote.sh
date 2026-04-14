#!/bin/bash
# Run the live-forecast ML pipeline locally and ship results to a remote
# autoresearch-macro checkout (typically on the production MacroLab VPS).
#
# Use case: the remote MacroLab host is too small to run Chronos-2
# (no GPU, limited RAM/disk), so heavy compute happens on a workstation
# with GPUs. Only the resulting live_forecasts.json (~tens of KB) is
# transferred; the remote publish_to_macrolab.sh then rebuilds the
# manifest and updates the MacroLab DB row.
#
# Prerequisites on the workstation:
#   * ML deps installed: `uv sync --extra ml`
#   * .env with FRED_API_KEY (and other source keys as needed)
#   * SSH access to the remote (key-based; this script does not
#     prompt for passwords)
#   * Remote has autoresearch-macro checked out and webapp/_site
#     already rendered
#
# Typical invocation (single country, default remote):
#   ./scripts/publish_live_to_remote.sh \
#       --remote deploy@macrolab.no \
#       --countries norway

set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)

REMOTE="${REMOTE:-}"
REMOTE_PROJECT_ROOT="${REMOTE_PROJECT_ROOT:-/opt/autoresearch-macro}"
COUNTRIES="norway,canada,sweden"
ORIGIN=""
SKIP_DATA=0
SKIP_MODELS=0
DRY_RUN=0
PUBLISH_ARGS=()

usage() {
    cat <<EOF
Usage: $(basename "$0") --remote USER@HOST [options] [-- publish_args...]

Generates live quantile forecasts on this machine and pushes only the
resulting live_forecasts.json to a remote autoresearch-macro checkout,
then triggers the remote's publish_to_macrolab.sh --skip-build to
rebuild the manifest and sync the MacroLab DB.

Required:
  --remote USER@HOST          SSH target (or set \$REMOTE)

Options:
  --remote-project-root PATH  Path to autoresearch-macro on remote
                              (default: \$REMOTE_PROJECT_ROOT or
                              /opt/autoresearch-macro)
  --countries LIST            Comma-separated subset (default: all three)
  --origin YYYY-MM-DD         Forecast origin date (default: today UTC)
  --skip-data                 Don't refresh data, reuse cached parquet panels
  --skip-models               Don't re-run forecasts, reuse results/live/*.json
  --dry-run                   Print commands but skip rsync + remote ssh
  -h, --help                  Show this help text

Anything after -- is appended verbatim to the remote publish_to_macrolab.sh
command (useful for things like --paper-url, --repo-url).
EOF
}

run() {
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
    if [[ "${DRY_RUN}" -eq 0 ]]; then
        "$@"
    fi
}

forwarding=0
while [[ $# -gt 0 ]]; do
    if [[ "${forwarding}" -eq 1 ]]; then
        PUBLISH_ARGS+=("$1"); shift; continue
    fi
    case "$1" in
        --remote) REMOTE="$2"; shift 2 ;;
        --remote-project-root) REMOTE_PROJECT_ROOT="$2"; shift 2 ;;
        --countries) COUNTRIES="$2"; shift 2 ;;
        --origin) ORIGIN="$2"; shift 2 ;;
        --skip-data) SKIP_DATA=1; shift ;;
        --skip-models) SKIP_MODELS=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --) forwarding=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ -z "${REMOTE}" ]]; then
    echo "ERROR: --remote USER@HOST is required (or set \$REMOTE)" >&2
    exit 1
fi

cd "${PROJECT_ROOT}"

if [[ -n "${PYTHON_BIN:-}" ]]; then
    PYTHON_RUNNER=("${PYTHON_BIN}")
elif [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON_RUNNER=("${PROJECT_ROOT}/.venv/bin/python")
else
    PYTHON_RUNNER=(uv run python)
fi

IFS=',' read -ra COUNTRY_ARR <<< "${COUNTRIES}"

# --------------------------------------------------------------------------
# Step 1 — refresh local data
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Step 2 — local live forecasts (Chronos-2 quantiles + BVAR + ETS)
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Step 3 — assemble consolidated JSON
# --------------------------------------------------------------------------
run "${PYTHON_RUNNER[@]}" scripts/build_live_forecasts_json.py

# --------------------------------------------------------------------------
# Step 4 — ship JSON to remote
# --------------------------------------------------------------------------
LOCAL_JSON="${PROJECT_ROOT}/webapp/_data/live_forecasts.json"
REMOTE_JSON="${REMOTE_PROJECT_ROOT}/webapp/_data/live_forecasts.json"

if [[ "${DRY_RUN}" -eq 0 && ! -f "${LOCAL_JSON}" ]]; then
    echo "ERROR: live_forecasts.json was not produced at ${LOCAL_JSON}" >&2
    exit 1
fi

remote_dir=$(dirname "${REMOTE_JSON}")
run ssh "${REMOTE}" "mkdir -p $(printf '%q' "${remote_dir}")"
run rsync -av "${LOCAL_JSON}" "${REMOTE}:${REMOTE_JSON}"

# --------------------------------------------------------------------------
# Step 5 — trigger remote publish (manifest rebuild + DB sync via docker)
# --------------------------------------------------------------------------
remote_cmd="cd $(printf '%q' "${REMOTE_PROJECT_ROOT}") && ./scripts/publish_to_macrolab.sh --skip-build"
if [[ "${#PUBLISH_ARGS[@]}" -gt 0 ]]; then
    for arg in "${PUBLISH_ARGS[@]}"; do
        remote_cmd+=" $(printf '%q' "${arg}")"
    done
fi
run ssh "${REMOTE}" "${remote_cmd}"

echo
echo "Live forecasts published: $(hostname) → ${REMOTE}:${REMOTE_PROJECT_ROOT}"
