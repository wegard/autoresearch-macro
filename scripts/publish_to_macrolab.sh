#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH='' cd -- "${SCRIPT_DIR}/.." && pwd)

PROJECT_SLUG="${PROJECT_SLUG:-autoresearch-macro}"
PROJECT_NAME="${PROJECT_NAME:-Autoresearch Macro}"
PROJECT_DESCRIPTION="${PROJECT_DESCRIPTION:-Interactive research dashboard for agentic macro forecasting experiments.}"
PROJECT_HEADLINE="${PROJECT_HEADLINE:-Agentic search over macro forecasting pipelines across Norway, Canada, and Sweden}"
APP_LABEL="${APP_LABEL:-Open Autoresearch Analysis}"
LIFECYCLE_STATUS="${LIFECYCLE_STATUS:-preview}"

MACROLAB_ROOT="${MACROLAB_ROOT:-/opt/macrolab}"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-${MACROLAB_ROOT}/project-artifacts}"
RELEASE_STAMP="${RELEASE_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
REPO_URL="${REPO_URL:-}"
PAPER_URL="${PAPER_URL:-}"

SKIP_BUILD=0
RENDER_ONLY=0
SKIP_SYNC=0
SYNC_MODE="auto"  # auto | docker | host

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
  --sync-mode MODE       'auto' (default), 'docker', or 'host'.
                         'auto' uses docker compose if both
                         docker-compose.prod.yml and .env.production
                         are present under --macrolab-root.
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
        --sync-mode)
            SYNC_MODE="$2"
            case "${SYNC_MODE}" in
                auto|docker|host) ;;
                *) echo "ERROR: --sync-mode must be one of auto|docker|host" >&2; exit 1 ;;
            esac
            shift 2
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
LIVE_DATA_PATH="${PROJECT_ROOT}/webapp/_data/live_forecasts.json"
MANIFEST_PATH="${RELEASE_DIR}/macrolab-manifest.json"
SYNC_SCRIPT="${MACROLAB_ROOT}/scripts/sync_project_publication.py"
PUBLISHED_URL="/published/${PROJECT_SLUG}/index.html"
LIVE_DATA_URL="/published/${PROJECT_SLUG}/live_forecasts.json"

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

# Copy the live forecasts JSON alongside the rendered site so MacroLab's
# frontend can fetch it directly from the published static directory.
if [[ -f "${LIVE_DATA_PATH}" ]]; then
    run cp "${LIVE_DATA_PATH}" "${RELEASE_DIR}/live_forecasts.json"
else
    echo "Note: no live_forecasts.json at ${LIVE_DATA_PATH}; manifest will omit live_data_url."
fi

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

if [[ -f "${LIVE_DATA_PATH}" ]]; then
    manifest_cmd+=(--live-data-url "${LIVE_DATA_URL}")
fi

if [[ -n "${APP_LABEL}" ]]; then
    manifest_cmd+=(--app-label "${APP_LABEL}")
fi

run "${manifest_cmd[@]}"

# Copy the release into the public directory so Caddy can serve it.
# Caddy only bind-mounts ${PUBLIC_DIR} in docker-compose.prod.yml, not the
# parent ${ARTIFACT_ROOT}, so a symlink from public/ -> releases/ would
# dangle inside the container. Keep the release archive under releases/
# for history, but put the served files directly under public/.
if [[ -L "${PUBLIC_LINK}" ]]; then
    run rm "${PUBLIC_LINK}"
fi
run mkdir -p "${PUBLIC_LINK}"
run rsync -a --delete "${RELEASE_DIR}/" "${PUBLIC_LINK}/"

# --------------------------------------------------------------------------
# MacroLab metadata sync
# --------------------------------------------------------------------------
#
# Two delivery modes:
#   * docker — invoke the bundled sync script inside a one-shot
#     macrolab-backend container so it can reach postgres on the docker
#     network. Required on the production VPS where postgres is not exposed
#     to the host.
#   * host — invoke the sync script with the host venv / uv. Works for local
#     dev deploys where MacroLab's own venv has DB access.
# --------------------------------------------------------------------------

COMPOSE_FILE="${MACROLAB_ROOT}/docker-compose.prod.yml"
COMPOSE_ENV_FILE="${MACROLAB_ROOT}/.env.production"

resolve_sync_mode() {
    if [[ "${SYNC_MODE}" != "auto" ]]; then
        printf '%s' "${SYNC_MODE}"
        return
    fi
    if [[ -f "${COMPOSE_FILE}" && -f "${COMPOSE_ENV_FILE}" ]] \
        && command -v docker >/dev/null 2>&1; then
        printf 'docker'
    else
        printf 'host'
    fi
}

# Read the image tag of the currently running backend container so the
# one-shot sync container matches. Without this, docker compose substitutes
# `${IMAGE_TAG:-latest}` and may pick a stale build that lacks new manifest
# fields, silently dropping them during pydantic validation. Returns empty
# string if discovery fails — caller decides how to handle.
discover_running_image_tag() {
    local image
    image=$(docker compose --env-file "${COMPOSE_ENV_FILE}" -f "${COMPOSE_FILE}" \
        ps macrolab-backend --format '{{.Image}}' 2>/dev/null | head -1)
    if [[ -n "${image}" && "${image}" == *":"* ]]; then
        printf '%s' "${image##*:}"
    fi
}

run_sync_docker() {
    local discovered_tag
    discovered_tag=$(discover_running_image_tag)
    if [[ -n "${discovered_tag}" ]]; then
        echo "Using IMAGE_TAG=${discovered_tag} (from running macrolab-backend container)"
        export IMAGE_TAG="${discovered_tag}"
    elif [[ -z "${IMAGE_TAG:-}" ]]; then
        echo "WARNING: macrolab-backend not running; falling back to IMAGE_TAG=latest. " \
             "If 'latest' is older than the deployed image, new manifest fields may be dropped."
    fi

    run docker compose \
        --env-file "${COMPOSE_ENV_FILE}" \
        -f "${COMPOSE_FILE}" \
        run --rm \
        -v "${MANIFEST_PATH}:/tmp/manifest.json:ro" \
        macrolab-backend \
        python /app/scripts/sync_project_publication.py \
        --manifest /tmp/manifest.json \
        --slug "${PROJECT_SLUG}" \
        --name "${PROJECT_NAME}" \
        --description "${PROJECT_DESCRIPTION}" \
        --lifecycle-status "${LIFECYCLE_STATUS}"
}

run_sync_host() {
    if [[ ! -f "${SYNC_SCRIPT}" ]]; then
        echo "MacroLab sync script not found at ${SYNC_SCRIPT}; skipping metadata sync."
        return
    fi
    local sync_cmd
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
}

if [[ "${SKIP_SYNC}" -eq 0 ]]; then
    EFFECTIVE_SYNC_MODE=$(resolve_sync_mode)
    echo "Sync mode: ${EFFECTIVE_SYNC_MODE} (requested: ${SYNC_MODE})"
    case "${EFFECTIVE_SYNC_MODE}" in
        docker) run_sync_docker ;;
        host)   run_sync_host ;;
        *) echo "ERROR: unsupported sync mode: ${EFFECTIVE_SYNC_MODE}" >&2; exit 1 ;;
    esac
fi

echo ""
echo "Published release:"
echo "  ${RELEASE_DIR}"
echo "Public artifact:"
echo "  ${PUBLISHED_URL}"
