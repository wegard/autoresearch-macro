#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)

PROJECT_SLUG="${PROJECT_SLUG:-autoresearch-macro}"
PROJECT_NAME="${PROJECT_NAME:-Autoresearch Macro}"
PROJECT_DESCRIPTION="${PROJECT_DESCRIPTION:-Interactive research dashboard for agentic macro forecasting experiments.}"
PROJECT_HEADLINE="${PROJECT_HEADLINE:-Agentic search over macro forecasting pipelines across Norway, Canada, and Sweden}"
LIFECYCLE_STATUS="${LIFECYCLE_STATUS:-preview}"

MACROLAB_ROOT="${MACROLAB_ROOT:-/opt/macrolab}"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-${MACROLAB_ROOT}/project-artifacts}"
RELEASE_STAMP="${RELEASE_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
REPO_URL="${REPO_URL:-}"
PAPER_URL="${PAPER_URL:-}"

SKIP_BUILD=0
RENDER_ONLY=0
SKIP_SYNC=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --artifact-root PATH   Override the MacroLab artifact root
  --macrolab-root PATH   Override the MacroLab checkout root
  --release-stamp STAMP  Override the UTC release stamp
  --repo-url URL         Add a repository link to the manifest
  --paper-url URL        Add a paper link to the manifest
  --skip-build           Reuse the existing webapp/_site output
  --render-only          Skip data regeneration, only run quarto render
  --skip-sync            Skip MacroLab metadata sync
  -h, --help             Show this help text
EOF
}

run() {
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
    "$@"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $1" >&2
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --artifact-root)
            ARTIFACT_ROOT="$2"
            shift 2
            ;;
        --macrolab-root)
            MACROLAB_ROOT="$2"
            shift 2
            ;;
        --release-stamp)
            RELEASE_STAMP="$2"
            shift 2
            ;;
        --repo-url)
            REPO_URL="$2"
            shift 2
            ;;
        --paper-url)
            PAPER_URL="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        --render-only)
            RENDER_ONLY=1
            shift
            ;;
        --skip-sync)
            SKIP_SYNC=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

RELEASES_DIR="${ARTIFACT_ROOT}/releases/${PROJECT_SLUG}"
PUBLIC_DIR="${ARTIFACT_ROOT}/public"
PUBLIC_LINK="${PUBLIC_DIR}/${PROJECT_SLUG}"
RELEASE_DIR="${RELEASES_DIR}/${RELEASE_STAMP}"
SITE_DIR="${PROJECT_ROOT}/webapp/_site"
MANIFEST_PATH="${RELEASE_DIR}/macrolab-manifest.json"
SYNC_SCRIPT="${MACROLAB_ROOT}/scripts/sync_project_publication.py"
PUBLISHED_URL="/published/${PROJECT_SLUG}/index.html"

cd "${PROJECT_ROOT}"

require_cmd rsync
require_cmd ln
require_cmd mkdir

if [[ -n "${PYTHON_BIN:-}" ]]; then
    PYTHON_RUNNER=("${PYTHON_BIN}")
elif [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON_RUNNER=("${PROJECT_ROOT}/.venv/bin/python")
else
    require_cmd uv
    export UV_CACHE_DIR="${UV_CACHE_DIR:-${PROJECT_ROOT}/.uv-cache}"
    PYTHON_RUNNER=(uv run python)
fi

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    require_cmd quarto
fi

echo "Publishing ${PROJECT_SLUG} to MacroLab"
echo "  Project root: ${PROJECT_ROOT}"
echo "  Artifact root: ${ARTIFACT_ROOT}"
echo "  Release stamp: ${RELEASE_STAMP}"
echo "  Published URL: ${PUBLISHED_URL}"
echo ""

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    if [[ "${RENDER_ONLY}" -eq 0 ]]; then
        run "${PYTHON_RUNNER[@]}" webapp/_data/prepare_results.py
    fi
    (
        cd "${PROJECT_ROOT}/webapp"
        run quarto render
    )
fi

if [[ ! -f "${SITE_DIR}/index.html" ]]; then
    echo "ERROR: expected rendered site at ${SITE_DIR}/index.html" >&2
    exit 1
fi

if [[ -e "${RELEASE_DIR}" ]]; then
    echo "ERROR: release directory already exists: ${RELEASE_DIR}" >&2
    exit 1
fi

run mkdir -p "${RELEASES_DIR}" "${PUBLIC_DIR}" "${RELEASE_DIR}"
run rsync -a --delete "${SITE_DIR}/" "${RELEASE_DIR}/"

manifest_cmd=(
    "${PYTHON_RUNNER[@]}"
    scripts/build_macrolab_manifest.py
    --output "${MANIFEST_PATH}"
    --entrypoint "${PUBLISHED_URL}"
    --headline "${PROJECT_HEADLINE}"
)

if [[ -n "${REPO_URL}" ]]; then
    manifest_cmd+=(--repo-url "${REPO_URL}")
fi

if [[ -n "${PAPER_URL}" ]]; then
    manifest_cmd+=(--paper-url "${PAPER_URL}")
fi

run "${manifest_cmd[@]}"
run ln -sfn "${RELEASE_DIR}" "${PUBLIC_LINK}"

if [[ "${SKIP_SYNC}" -eq 0 ]]; then
    if [[ -f "${SYNC_SCRIPT}" ]]; then
        if [[ -x "${MACROLAB_ROOT}/.venv/bin/python" ]]; then
            sync_cmd=(
                "${MACROLAB_ROOT}/.venv/bin/python" "${SYNC_SCRIPT}"
                --manifest "${MANIFEST_PATH}"
                --slug "${PROJECT_SLUG}"
                --name "${PROJECT_NAME}"
                --description "${PROJECT_DESCRIPTION}"
                --lifecycle-status "${LIFECYCLE_STATUS}"
            )
        else
            require_cmd uv
            sync_cmd=(
                uv run --project "${MACROLAB_ROOT}" python "${SYNC_SCRIPT}"
                --manifest "${MANIFEST_PATH}"
                --slug "${PROJECT_SLUG}"
                --name "${PROJECT_NAME}"
                --description "${PROJECT_DESCRIPTION}"
                --lifecycle-status "${LIFECYCLE_STATUS}"
            )
        fi
        run "${sync_cmd[@]}"
    else
        echo "MacroLab sync script not found at ${SYNC_SCRIPT}; skipping metadata sync."
    fi
fi

echo ""
echo "Published release:"
echo "  ${RELEASE_DIR}"
echo "Public artifact:"
echo "  ${PUBLISHED_URL}"
