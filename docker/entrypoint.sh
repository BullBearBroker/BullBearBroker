#!/usr/bin/env sh
set -e

if [ -n "${BULLBEAR_DB_URL}" ] && [ -z "${DATABASE_URL}" ]; then
  export DATABASE_URL="${BULLBEAR_DB_URL}"
fi

if [ "${BULLBEAR_MIGRATE_ON_START}" = "true" ]; then
  alembic upgrade head || true
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
else
  exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
fi
