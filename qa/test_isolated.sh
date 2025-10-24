#!/usr/bin/env bash
set -Eeuo pipefail

retry() {
  local max=${1:-5}
  local delay=${2:-2}
  shift 2
  local n=0
  until "$@"; do
    n=$((n + 1))
    if [ "$n" -ge "$max" ]; then
      echo "[ERR] Retry failed after $n attempts: $*" >&2
      return 1
    fi
    echo "[WARN] Retry $n/$max -> $*"
    sleep "$delay"
  done
}

MASK() { sed -E 's#(://[^:]+:)[^@]+(@)#\1********\2#g'; }

SCHEMA="test_$(date +%Y%m%d_%H%M%S)"
DROP_AFTER=false
PYTEST_OPTS=""
AI_PROVIDER_FOR_TESTS="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --schema) SCHEMA="$2"; shift 2;;
    --drop-after) DROP_AFTER=true; shift;;
    --pytest-opts) PYTEST_OPTS="$2"; shift 2;;
    --provider) AI_PROVIDER_FOR_TESTS="$2"; shift 2;;
    --provider=*) AI_PROVIDER_FOR_TESTS="${1#*=}"; shift;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

AI_PROVIDER_FOR_TESTS="$(printf '%s' "${AI_PROVIDER_FOR_TESTS}" | tr 'A-Z' 'a-z')"

if [[ -z "${SUPABASE_POOLER_URL:-}" ]]; then
  echo "[ERR] SUPABASE_POOLER_URL is required (Session Pooler DSN sin query)" >&2
  exit 2
fi

QS_BASE="sslmode=require"
if [[ "${SUPABASE_POOLER_URL}" == *"?"* ]]; then
  TEST_DB_URL="${SUPABASE_POOLER_URL}&${QS_BASE}"
else
  TEST_DB_URL="${SUPABASE_POOLER_URL}?${QS_BASE}"
fi

DOCKER_ENV_BASE=(
  -e APP_ENV=test
  -e TEST_SCHEMA="${SCHEMA}"
  -e SUPABASE_DB_POOL_URL="${TEST_DB_URL}"
  -e PYTHONPATH=.
)
DOCKER_ENV_TEST=("${DOCKER_ENV_BASE[@]}" -e AI_PROVIDER="${AI_PROVIDER_FOR_TESTS}")

echo "[QA] TEST_SCHEMA = ${SCHEMA}"
echo "[QA] Using pooler URL (masked): $(echo "${SUPABASE_POOLER_URL}" | MASK)"
echo "[QA] Final test URL (masked):   $(echo "${TEST_DB_URL}" | MASK)"

retry 6 2 docker compose exec -T "${DOCKER_ENV_BASE[@]}" api python - <<'PY'
import os, sqlalchemy as sa

url = os.environ["SUPABASE_DB_POOL_URL"]
schema = os.environ["TEST_SCHEMA"]

engine = sa.create_engine(
    url,
    pool_pre_ping=True,
    connect_args={"sslmode": "require", "prepare_threshold": None},
)

with engine.begin() as cx:
    cx.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    cx.exec_driver_sql(f'SET search_path TO "{schema}", public')

print("SCHEMA_OK")
PY

retry 3 2 docker compose exec -T "${DOCKER_ENV_BASE[@]}" \
  api bash -lc "DB_USE_POOL=true PGOPTIONS='-c search_path=${SCHEMA}' python backend/scripts/check_db_connectivity.py"

retry 3 2 docker compose exec -T "${DOCKER_ENV_BASE[@]}" \
  api bash -lc "PGOPTIONS='-c search_path=${SCHEMA}' alembic upgrade head && alembic current -v || true"

retry 5 2 docker compose exec -T "${DOCKER_ENV_BASE[@]}" \
  api bash -lc "PGOPTIONS='-c search_path=${SCHEMA}' python backend/scripts/seed_minimal_test_data.py"

docker compose exec -T "${DOCKER_ENV_TEST[@]}" \
  api python - <<'PY'
import os
import shlex
import subprocess
import sys

opts = shlex.split(os.environ.get("PYTEST_OPTS", ""))
cmd = ["pytest", "backend/tests"]
cmd.extend(opts)
if not any(flag in ("-q", "--quiet") for flag in opts):
    cmd.append("-q")

os.environ.setdefault("DB_USE_POOL", "true")
os.environ.setdefault("PGOPTIONS", f"-c search_path={os.environ['TEST_SCHEMA']}")
os.environ.setdefault("ENABLE_CAPTCHA_ON_LOGIN", "false")
os.environ.setdefault("SENTIMENT_ENABLED", "false")
os.environ.setdefault("POOL_SIZE", "5")
os.environ.setdefault("MAX_OVERFLOW", "5")
os.environ.setdefault("POOL_TIMEOUT", "10")
os.environ.setdefault("POOL_RECYCLE", "1800")
os.environ.setdefault("SQLALCHEMY_ECHO", "false")

sys.exit(subprocess.call(cmd))
PY
STATUS=$?

cleanup() {
  if $DROP_AFTER; then
    echo "[QA] Dropping schema ${SCHEMA}"
    docker compose exec -T "${DOCKER_ENV_BASE[@]}" api python - <<'PY'
import os, sqlalchemy as sa

url = os.environ['SUPABASE_DB_POOL_URL']
schema = os.environ['TEST_SCHEMA']
engine = sa.create_engine(
    url,
    pool_pre_ping=True,
    connect_args={'sslmode': 'require', 'prepare_threshold': None},
)

with engine.begin() as cx:
    cx.exec_driver_sql(
        f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE pid <> pg_backend_pid()
          AND usename = current_user
          AND query ILIKE '%"{schema}"%'
        """
    )
    cx.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

print('SCHEMA_DROPPED')
PY
  fi
}

trap cleanup EXIT

exit $STATUS
