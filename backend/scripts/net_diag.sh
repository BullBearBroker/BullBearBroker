#!/usr/bin/env bash
set -euo pipefail

# QA 2.1: Supabase network diagnostics helper (IPv4 aware)

HOST=$(python - <<'PY'
import os
import urllib.parse as u
fallback = "db.vhrmibwznobqvnaljzhz.supabase.co"
url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("SUPABASE_DB_POOL_URL")
if not url:
    print(fallback)
else:
    parsed = u.urlparse(url)
    print(parsed.hostname or fallback)
PY
)

echo "== NetDiag: DNS =="
getent hosts "$HOST" || true

echo "== NetDiag: IPv4 resolution (getent) =="
if command -v getent >/dev/null; then
  getent ahostsv4 "$HOST" | awk 'NR==1{print $1}' || echo "no IPv4 entries"
else
  echo "getent not installed"
fi

echo "== NetDiag: TCP reachability (5432/6543) =="
for PORT in 5432 6543; do
  if (echo > /dev/tcp/${HOST}/$PORT) >/dev/null 2>&1; then
    echo "OK: can reach port $PORT"
  else
    echo "WARN: cannot reach port $PORT"
  fi
done

echo "== NetDiag: traceroute (best-effort) =="
if command -v traceroute >/dev/null; then
  traceroute -n "$HOST" | head -n 10
else
  echo "traceroute not installed"
fi

echo "== NetDiag: psql smoke (best-effort) =="
if command -v psql >/dev/null; then
  if [[ -n "${SUPABASE_DB_URL:-}" ]]; then
    PGPASSWORD="$(python - <<'PY'
import os
import urllib.parse as u
url = os.environ.get("SUPABASE_DB_URL", "")
print(u.urlparse(url).password or "")
PY
)" psql "${SUPABASE_DB_URL}" -c "SELECT 1;" || echo "psql failed"
  else
    echo "SUPABASE_DB_URL not set"
  fi
else
  echo "psql not installed"
fi

echo "NetDiag done."
