#!/usr/bin/env bash
# BullBearBroker – direct DB bridge helper (IPv4 -> IPv6 via socat)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "${PROJECT_ROOT}"

log() {
  printf '# QA: %s\n' "$*" >&2
}

fatal() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || fatal "falta el binario requerido '${cmd}'"
}

log "iniciando flujo DIRECT DB (IPv4 → IPv6 bridge)"

require_cmd docker
require_cmd make
require_cmd curl
require_cmd jq
require_cmd nc
require_cmd python3

if ! command -v socat >/dev/null 2>&1; then
  require_cmd brew
  log "instalando socat via Homebrew"
  brew install socat >/dev/null
fi

if ! docker info >/dev/null 2>&1; then
  fatal "Docker no está activo"
fi

ENV_PATH="backend/.env.local"
ENV_EXAMPLE="backend/.env.example"

if [[ ! -f "${ENV_PATH}" ]]; then
  if [[ -f "${ENV_EXAMPLE}" ]]; then
    cp "${ENV_EXAMPLE}" "${ENV_PATH}"
    log "backend/.env.local creado desde backend/.env.example"
  else
    touch "${ENV_PATH}"
    log "backend/.env.local creado vacío (sin ejemplo disponible)"
  fi
fi

export BBB_PROJECT_ROOT="${PROJECT_ROOT}"
export BBB_BRIDGE_HOST="host.docker.internal"
export BBB_BRIDGE_PORT="55432"
export BBB_DIRECT_USER="${SUPABASE_DIRECT_USER:-}"
export BBB_DIRECT_PASS_URLENC="${SUPABASE_DIRECT_PASS_URLENC:-}"
export BBB_DIRECT_DB_NAME="${SUPABASE_DIRECT_DB_NAME:-postgres}"

TMP_ENV_LOG="$(mktemp /tmp/bbb_direct_env_update.XXXXXX.log)"
python3 scripts/helpers/update_direct_db_env.py >"${TMP_ENV_LOG}" 2>&1 || {
  tail -n 20 "${TMP_ENV_LOG}" >&2
  fatal "falló la actualización de backend/.env.local (ver log anterior)"
}
rm -f "${TMP_ENV_LOG}"
log ".env.local actualizado para puente directo"

SOCAT_LOG="/tmp/bbb_socat_ipv4_to_ipv6.log"
HOST_SUPA="${SUPABASE_BRIDGE_TARGET_HOST:-db.vhrmibwznobqvnaljzhz.supabase.co}"

pkill -f "socat .*${BBB_BRIDGE_PORT}" >/dev/null 2>&1 && log "puente socat previo detenido" || log "sin procesos socat previos"

log "levantando puente socat (${BBB_BRIDGE_HOST}:${BBB_BRIDGE_PORT} → ${HOST_SUPA}:5432)"
(
  nohup socat -d -d "TCP4-LISTEN:${BBB_BRIDGE_PORT},reuseaddr,fork" "TCP6:${HOST_SUPA}:5432" >"${SOCAT_LOG}" 2>&1 < /dev/null &
) >/dev/null 2>&1

sleep 1
if ! nc -z 127.0.0.1 "${BBB_BRIDGE_PORT}" >/dev/null 2>&1; then
  log "el puente socat no está escuchando; últimas líneas del log:"
  tail -n 40 "${SOCAT_LOG}" >&2 || true
  fatal "socat no pudo inicializarse (ver log en ${SOCAT_LOG})"
fi
log "puente socat activo (log: ${SOCAT_LOG})"

log "reiniciando stack docker compose"
docker compose down >/dev/null 2>&1 || log "docker compose down devolvió código no cero (se ignora)"
docker compose up -d --build

log "db-smoke"
make db-smoke

log "db-migrate-direct"
make db-migrate-direct

log "healthcheck backend"
curl -s http://127.0.0.1:8000/api/health | jq .

log "flujo completado"
echo "=========================================="
echo "✅ DIRECTO por puente IPv4→IPv6 operativo"
echo "• URL dentro del contenedor: host.docker.internal:${BBB_BRIDGE_PORT} (→ 5432 con TLS)"
echo "• Log del puente: ${SOCAT_LOG}"
echo "• Para detener el puente: pkill -f \"socat .*${BBB_BRIDGE_PORT}\""
echo "=========================================="
