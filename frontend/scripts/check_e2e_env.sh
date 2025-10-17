#!/bin/bash

echo "🔍 Verificando entorno E2E de Playwright..."
pnpm list @playwright/test playwright --depth 3 | grep playwright
echo "✅ Debe mostrarse una sola versión emparejada de @playwright/test y playwright"
