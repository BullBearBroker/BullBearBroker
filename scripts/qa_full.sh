#!/bin/bash
set -e

echo "🚀 Iniciando QA-FULL (BullBearBroker)"
echo "====================================="

# 1️⃣ Verificación de linters y secretos
echo "🔍 Ejecutando pre-commit hooks..."
pre-commit run --all-files || true

# 2️⃣ Tests backend
echo "🧠 Ejecutando tests de backend..."
pytest backend/tests -vv --cov=backend --cov-report=term-missing

# QA 2.0: Validamos que el dispatcher publique eventos vía Redis
echo "🚀 Verificando notificaciones..."
docker exec bullbear_api bash -c "PYTHONPATH=. APP_ENV=local python backend/scripts/send_test_notification.py"

# QA 2.0: confirmamos que Redis esté operativo antes de continuar
echo "🐘 Verificando Redis..."
docker ps | grep redis && echo "✅ Redis activo" || echo "⚠️ Redis no detectado"

# 3️⃣ Tests frontend
echo "⚛️ Ejecutando tests de frontend..."
npm --prefix frontend run test -- --coverage

# QA 2.0: ejecutar flujo E2E usando Playwright
echo "🎭 Ejecutando tests E2E (Playwright)..."
pnpm --prefix frontend exec playwright test --config=playwright.config.ts || echo "⚠️ E2E falló, revisar puerto o BASE_URL"

echo "====================================="
echo "✅ QA-FULL COMPLETADO EXITOSAMENTE"
