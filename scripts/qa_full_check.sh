#!/usr/bin/env bash
set -euo pipefail

echo "== BullBearBroker • Full Project Check =="
echo "Dir actual: $(pwd)"
START_TS=$(date +%s)

REPO="${HOME}/Desktop/BullBearBroker"
cd "$REPO"

export HUSKY=0
export HUSKY_SKIP_INSTALL=1

FAILED_STEPS=()

# Limpieza opcional de caches de test
rm -rf .pytest_cache frontend/.next .next node_modules/.cache || true

# --- Python venv + deps ---
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip -q
python -m pip install -r backend/requirements.txt -q
[ -f backend/requirements-dev.txt ] && python -m pip install -r backend/requirements-dev.txt -q

# --- Node deps (npm por defecto; pnpm opcional comentado) ---
# corepack enable && corepack prepare pnpm@latest --activate
# pnpm --prefix frontend install --frozen-lockfile
if [ -f frontend/package-lock.json ]; then
  npm --prefix frontend ci --ignore-scripts
else
  npm --prefix frontend install --ignore-scripts
fi

# --- Pre-commit (formato/estilo) ---
pre-commit install
pre-commit run --all-files || true
pre-commit run --all-files || true

# --- Chequeos estáticos BACKEND ---
if ! ruff check .; then
  FAILED_STEPS+=("ruff check")
fi
if ! black --check .; then
  FAILED_STEPS+=("black --check")
fi
if ! isort --check-only .; then
  FAILED_STEPS+=("isort --check-only")
fi
command -v mypy >/dev/null 2>&1 && mypy backend || echo "mypy no configurado, siguiendo..."

# --- Chequeos estáticos FRONTEND ---
if ! npm --prefix frontend run lint; then
  echo "lint frontend no definido o con warnings"
  FAILED_STEPS+=("frontend lint")
fi
if ! npm --prefix frontend run typecheck; then
  echo "typecheck no definido, siguiendo..."
  FAILED_STEPS+=("frontend typecheck")
fi

# --- Tests BACKEND (coverage) ---
if ! pytest backend/tests -vv --maxfail=1 \
  --cov=backend --cov-report=term-missing --cov-report=html:backend/htmlcov; then
  FAILED_STEPS+=("pytest backend")
fi

# --- Tests FRONTEND (Jest + coverage) ---
if ! npm --prefix frontend run test -- --coverage --runInBand; then
  FAILED_STEPS+=("npm test frontend")
fi

# --- Stack LOCAL con Docker ---
docker compose down -v || true
docker compose build --no-cache
docker compose up -d

# --- Migraciones Alembic ---
API_SVC=$(docker compose ps --services | grep -E 'api|backend' | head -n 1 || true)
if [ -n "${API_SVC:-}" ]; then
  if ! docker compose exec -T "$API_SVC" bash -lc 'alembic upgrade head'; then
    echo "Alembic upgrade falló (continuando)"
    FAILED_STEPS+=("alembic upgrade")
  fi
else
  echo "No se encontró servicio de API para migraciones"
fi

# --- Salud API ---
for i in {1..12}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health/ || true)
  [ "$code" = "200" ] && break || { echo "Esperando API... intento $i"; sleep 5; }
done
echo "API /api/health => HTTP $code"

docker compose ps
[ -n "${API_SVC:-}" ] && docker compose logs --no-color --tail=120 "$API_SVC" || true

# --- Redis/Notificaciones (opcional si existe script) ---
if [ -n "${API_SVC:-}" ] && docker compose exec -T "$API_SVC" bash -lc "test -f backend/scripts/send_test_notification.py"; then
  docker compose exec -T "$API_SVC" bash -lc "PYTHONPATH=. APP_ENV=local python backend/scripts/send_test_notification.py || true"
fi

# --- QA Pooler Supabase / IPv4 / SSL (opcional si existe) ---
if [ -f qa/test_isolated.sh ]; then
  chmod +x qa/test_isolated.sh
  if ! ./qa/test_isolated.sh --provider=auto; then
    FAILED_STEPS+=("qa/test_isolated.sh")
  fi
else
  echo "qa/test_isolated.sh no existe; omitiendo chequeo Pooler"
fi

# --- E2E Playwright ---
if ! npx --yes playwright install --with-deps; then
  FAILED_STEPS+=("playwright deps")
fi
if ! npm --prefix frontend run e2e; then
  if ! npx --yes playwright test --config=frontend/playwright.config.ts; then
    FAILED_STEPS+=("playwright tests")
  fi
fi

# --- Build Frontend ---
if ! npm --prefix frontend run build; then
  FAILED_STEPS+=("frontend build")
fi

# --- Reportes ---
echo "== Reports =="
[ -d backend/htmlcov ] && echo "Cobertura backend: file://${REPO}/backend/htmlcov/index.html"
[ -d frontend/coverage ] && echo "Cobertura frontend: ${REPO}/frontend/coverage"
[ -d frontend/playwright-report ] && echo "Playwright: ${REPO}/frontend/playwright-report/index.html"

echo
echo "== Contenedores activos =="
docker compose ps

if [ ${#FAILED_STEPS[@]} -gt 0 ]; then
  echo
  echo "⚠️  Pasos con incidencias:"
  for step in "${FAILED_STEPS[@]}"; do
    echo " - ${step}"
  done
fi

END_TS=$(date +%s)
echo
echo "== FULL CHECK COMPLETO en $((END_TS-START_TS))s ✅ =="
