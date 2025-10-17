#!/usr/bin/env bash
set -euo pipefail

echo "# QA 2.8: Checking Alembic"
if [[ ! -d backend/alembic/versions ]]; then
  echo "ERROR: backend/alembic/versions no existe" >&2
  exit 1
fi

if ls -1 backend/alembic 2>/dev/null | grep -qi disabled; then
  echo "ERROR: found disabled migrations directory" >&2
  exit 1
fi

APP_ENV=staging alembic history | tail -n +1 >/dev/null

echo "OK: Alembic sanity passed"
