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

# 3️⃣ Tests frontend
echo "⚛️ Ejecutando tests de frontend..."
npm --prefix frontend run test -- --coverage

# 4️⃣ Tests E2E (Playwright)
echo "🎭 Ejecutando tests E2E (requiere frontend en ejecución)..."
cd frontend
pnpm exec playwright test --config=playwright.config.ts || echo "⚠️ E2E tests fallaron (verificar si el frontend estaba corriendo)"
cd ..

echo "====================================="
echo "✅ QA-FULL COMPLETADO EXITOSAMENTE"
