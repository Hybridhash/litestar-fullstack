#!/usr/bin/env bash
set -euo pipefail

# Railway deploy helper for web + SAQ worker split in this repository.
# This script is idempotent and safe to rerun.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

APP_SERVICE_NAME="${APP_SERVICE_NAME:-Litestar Web Frontend}"
WORKER_SERVICE_NAME="${WORKER_SERVICE_NAME:-SAQ Worker}"
PROJECT_NAME="${PROJECT_NAME:-}"
DETACH=true
SKIP_SETUP=false

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err() { echo -e "${RED}[ERR]${NC} $1"; }

usage() {
  cat <<'EOF'
Usage: ./tools/deploy/railway/deploy.sh [--ci] [--skip-setup] [--project-name NAME]

Options:
  --ci                  Stream deployment output instead of detached deploy.
  --skip-setup          Skip service/database/config setup, deploy only.
  --project-name NAME   Run railway init when no project is linked.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ci)
      DETACH=false
      shift
      ;;
    --skip-setup)
      SKIP_SETUP=true
      shift
      ;;
    --project-name)
      PROJECT_NAME="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_err "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_err "Missing required command: $1"
    exit 1
  fi
}

ensure_linked_project() {
  cd "${PROJECT_ROOT}"
  if railway status --json >/dev/null 2>&1; then
    log_ok "Project already linked."
    return
  fi

  if [[ -z "${PROJECT_NAME}" ]]; then
    log_err "No Railway project linked. Pass --project-name NAME or run 'railway link' first."
    exit 1
  fi

  log_info "Initializing Railway project '${PROJECT_NAME}'..."
  railway init --name "${PROJECT_NAME}"
  log_ok "Project initialized."
}

service_exists() {
  local service_name="$1"
  railway status --json | jq -e --arg NAME "${service_name}" '.services.edges[]?.node | select(.name == $NAME)' >/dev/null
}

ensure_service() {
  local service_name="$1"
  if service_exists "${service_name}"; then
    log_ok "Service exists: ${service_name}"
    return
  fi
  log_info "Creating service: ${service_name}"
  railway add --service "${service_name}"
  log_ok "Created service: ${service_name}"
}

ensure_database() {
  local db_name="$1"
  if railway status --json | grep -qi "${db_name}"; then
    log_ok "${db_name} already exists."
    return
  fi
  log_info "Provisioning ${db_name}..."
  railway add --database "${db_name}"
  log_ok "${db_name} provisioned."
}

service_id() {
  local service_name="$1"
  railway status --json | jq -r --arg NAME "${service_name}" '.services.edges[]?.node | select(.name == $NAME) | .id' | head -1
}

apply_config_patch() {
  local patch_json="$1"
  local message="$2"
  railway environment edit -m "${message}" --json <<<"${patch_json}"
}

configure_service_runtime() {
  local service_name="$1"
  local start_command="$2"
  local include_healthcheck="$3"
  local sid
  sid="$(service_id "${service_name}")"
  if [[ -z "${sid}" ]]; then
    log_err "Unable to resolve service id for ${service_name}"
    exit 1
  fi

  local patch
  if [[ "${include_healthcheck}" == "true" ]]; then
    patch="$(jq -n \
      --arg sid "${sid}" \
      --arg cmd "${start_command}" \
      '{
        services: {
          ($sid): {
            build: { builder: "NIXPACKS" },
            deploy: {
              runtime: "V2",
              numReplicas: 1,
              sleepApplication: false,
              restartPolicyType: "ON_FAILURE",
              restartPolicyMaxRetries: 5,
              healthcheckPath: "/health",
              healthcheckTimeout: 300,
              startCommand: $cmd
            }
          }
        }
      }'
    )"
  else
    patch="$(jq -n \
      --arg sid "${sid}" \
      --arg cmd "${start_command}" \
      '{
        services: {
          ($sid): {
            build: { builder: "NIXPACKS" },
            deploy: {
              runtime: "V2",
              numReplicas: 1,
              sleepApplication: false,
              restartPolicyType: "ON_FAILURE",
              restartPolicyMaxRetries: 5,
              startCommand: $cmd
            }
          }
        }
      }'
    )"
  fi

  apply_config_patch "${patch}" "configure ${service_name} runtime"
  log_ok "Configured runtime for ${service_name}"
}

ensure_secret_key() {
  railway service link "${APP_SERVICE_NAME}" >/dev/null
  local secret
  secret="$(railway variables --kv 2>/dev/null | sed -n 's/^SECRET_KEY=//p' | head -1 || true)"
  if [[ -n "${secret}" ]]; then
    echo "${secret}"
    return
  fi
  openssl rand -base64 32 | tr -d '=' | tr '+/' '-_'
}

configure_vars() {
  local secret_key="$1"

  railway service link "${APP_SERVICE_NAME}" >/dev/null
  railway variables \
    --set "SECRET_KEY=${secret_key}" \
    --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}' \
    --set 'REDIS_URL=${{Redis.REDIS_URL}}' \
    --set "LITESTAR_PORT=8000" \
    --set "LITESTAR_DEBUG=false" \
    --set "VITE_DEV_MODE=false" \
    --set "SAQ_USE_SERVER_LIFESPAN=false" \
    --skip-deploys >/dev/null
  log_ok "Configured web service variables."

  railway service link "${WORKER_SERVICE_NAME}" >/dev/null
  railway variables \
    --set "SECRET_KEY=${secret_key}" \
    --set 'DATABASE_URL=${{Postgres.DATABASE_URL}}' \
    --set 'REDIS_URL=${{Redis.REDIS_URL}}' \
    --set "LITESTAR_DEBUG=false" \
    --set "VITE_DEV_MODE=false" \
    --set "SAQ_USE_SERVER_LIFESPAN=false" \
    --set "SAQ_WEB_ENABLED=false" \
    --skip-deploys >/dev/null
  log_ok "Configured worker service variables."
}

deploy_service() {
  local service_name="$1"
  local message="$2"
  if [[ "${DETACH}" == "true" ]]; then
    railway up --detach --service "${service_name}" -m "${message}"
  else
    railway up --ci --service "${service_name}" -m "${message}"
  fi
}

main() {
  require_command railway
  require_command jq
  require_command openssl
  cd "${PROJECT_ROOT}"

  if ! railway whoami --json >/dev/null 2>&1; then
    log_err "Railway CLI is not authenticated. Run: railway login"
    exit 1
  fi

  ensure_linked_project

  if [[ "${SKIP_SETUP}" != "true" ]]; then
    ensure_database postgres
    ensure_database redis
    ensure_service "${APP_SERVICE_NAME}"
    ensure_service "${WORKER_SERVICE_NAME}"

    configure_service_runtime \
      "${APP_SERVICE_NAME}" \
      "app database upgrade --no-prompt && app run --host 0.0.0.0 --port \${PORT:-8000}" \
      "true"
    configure_service_runtime \
      "${WORKER_SERVICE_NAME}" \
      "app workers run" \
      "false"

    secret_key="$(ensure_secret_key)"
    configure_vars "${secret_key}"
  fi

  deploy_service "${APP_SERVICE_NAME}" "deploy web service"
  deploy_service "${WORKER_SERVICE_NAME}" "deploy worker service"

  log_ok "Deploy commands submitted."
  log_info "Check status with:"
  log_info "  railway service link \"${APP_SERVICE_NAME}\" && railway service status --json"
  log_info "  railway service link \"${WORKER_SERVICE_NAME}\" && railway service status --json"
}

main "$@"
