# ================================
# 🚀 BullBearBroker Makefile Final
# ================================

.PHONY: venv dev test lint fmt migrate up-local up-staging down build run ci verify-all clean
.PHONY: qa-backend qa-backend-cov qa-frontend qa-full qa-rebuild qa-db-smoke qa-migrate-local qa-db-smoke-local qa-backend-parallel qa-backend-serial
.PHONY: lint-backend lint-frontend fmt-backend fmt-frontend test-backend test-backend-cov test-frontend-cov test-e2e test-e2e-report health env-validate-backend env-validate-frontend env-sync push-test push-info push-prune secrets-scan

# Variables por defecto
ENV ?= local
APP ?= backend.main:app
PORT ?= 8000

# --- 🧠 ENTORNO VIRTUAL Y DEPENDENCIAS ---
venv:
	@echo "⚙️ Creando entorno virtual y instalando dependencias..."
	python3 -m venv .venv && . .venv/bin/activate && \
	pip install -r backend/requirements.txt && \
	pip install -r backend/requirements-dev.txt

# --- 🐳 DOCKER COMPOSE ---
dev:
	@echo "🐳 Levantando entorno completo con Docker Compose..."
	docker compose up --build

down:
	@echo "🧹 Deteniendo contenedores..."
	docker compose down

build:
	@echo "🔧 Construyendo imagen Docker local..."
	docker build -t bullbear:local .

rebuild-backend:
	@echo "♻️ Reconstruyendo backend sin cache..."
	@docker compose build --no-cache backend  # QA 2.0: limpia cache y reinstala dependencias

run:
	@echo "🚀 Ejecutando contenedor local en puerto 8000..."
	docker run --rm -p 8000:8000 bullbear:local

net-diag:
	@docker compose exec -T api bash -lc 'bash backend/scripts/net_diag.sh || true'

db-check:
	@docker compose exec -T api bash -lc 'PYTHONPATH=. APP_ENV=staging python backend/scripts/check_db_connectivity.py || true'

health:
	@curl -s -o - http://127.0.0.1:8000/api/health || true

# --- 🔐 ENV VALIDATION ---
env-validate-backend:
	@docker compose exec -T api bash -lc 'PYTHONPATH=. python backend/scripts/validate_env.py || true'

env-validate-frontend:
	@pnpm --prefix frontend run validate:env || true

env-sync:
	@python tools/sync_env_examples.py

# QA: Helpers para Web Push
push-test:
	@docker compose exec -T api bash -lc 'PYTHONPATH=. APP_ENV=staging python backend/scripts/send_test_push.py || true'

push-info:
	@echo "Frontend VAPID key: $${NEXT_PUBLIC_VAPID_PUBLIC_KEY}"
	@docker compose exec -T api bash -lc 'if [ -n "$${VAPID_PRIVATE_KEY}" ]; then echo "Backend VAPID present: yes"; else echo "Backend VAPID present: no"; fi' || true

push-prune:
	@docker compose exec -T api bash -lc 'PYTHONPATH=. APP_ENV=staging python backend/scripts/prune_stale_push_subs.py || true'

db-force-ipv4:
	@python backend/scripts/force_ipv4_env.py || true

db-smoke:
	@docker compose exec -T api bash -lc 'PYTHONPATH=. APP_ENV=staging python backend/scripts/check_db_connectivity.py'

db-migrate-direct:
	@docker compose exec -T api bash -lc 'export DATABASE_URL="$$SUPABASE_DB_URL"; alembic upgrade head'

secrets-scan:
	@mkdir -p qa
	@python tools/secrets_sweep.py || true
	@echo "Secrets report: qa/SECRETS_REPORT.md"

# --- ⚙️ BACKEND LOCAL ---
up-local:
	@echo "🚀 Iniciando stack en modo local con Docker Compose..."
	@docker compose up -d  # CODEx: alineado con la receta solicitada para entorno local

up-staging:
	@echo "🚀 Iniciando stack en modo staging..."
	@APP_ENV=staging docker compose up -d  # CODEx: permite levantar servicios con variables de staging

run-backend:
	@echo "🚀 Ejecutando backend en modo desarrollo con recarga automática..."
	@ENV=$(ENV) uvicorn $(APP) --reload --port $(PORT)  # CODEx: mantenemos tarea previa como alias útil

frontend-staging:
	@echo "🚀 Iniciando frontend en modo staging..."
	@NEXT_PUBLIC_ENV=staging pnpm --prefix frontend dev --port 3001

# --- 🧩 MIGRACIONES ---
migrate:
	@echo "🧩 Aplicando migraciones Alembic..."
	@cd backend && alembic upgrade head

# --- ✅ TESTS ---
test:
	@echo "🧪 Ejecutando suite de tests del backend..."
	@pytest backend/tests -vv

test-frontend:
	@echo "🧪 Ejecutando tests del frontend (Jest) – modo tolerante..."
	@pnpm --prefix frontend run test -- --passWithNoTests

test-all:
	@echo "🔄 Ejecutando validaciones completas (lint + backend + frontend)..."
	@pre-commit run --all-files || true  # CODEx: ejecutar hooks de forma no bloqueante
	@pytest backend/tests -vv  # CODEx: validar suite de backend en modo detallado
	@pnpm --prefix frontend run test:dev  # CODEx: ejecutar suite unitaria/integración del frontend sin UI

# QA: Backend tests (smoke & cobertura unificada)
test-backend:
	@pytest backend/tests -q

test-backend-cov:
	@mkdir -p qa
	@pytest backend/tests -q --cov=backend --cov-report=term-missing --cov-report=xml:qa/backend-coverage.xml

# QA: Frontend tests con artefactos en qa/
test-frontend-cov:
	@mkdir -p qa/frontend-coverage
	@pnpm --prefix frontend run test -- --coverage --coverageReporters=text --coverageReporters=cobertura --coverageDirectory=qa/frontend-coverage

# --- 🔍 LINTERS Y FORMATO ---
lint:
	@echo "🔍 Ejecutando linters (black, ruff, isort, detect-secrets)..."
	@pre-commit run --all-files || true

fmt:
	@echo "🧹 Formateando código (black + ruff + isort)..."
	@black . && ruff --fix . && isort .

format:
	@echo "🧹 Formateando código base siguiendo la receta solicitada..."
	@black .  # CODEx: formateo estandarizado de Python
	@isort .  # CODEx: ordenar imports antes de chequear estilo
	@ruff check .  # CODEx: mantiene análisis estático en modo verificación

# QA: Linters/formatters unificados
lint-backend:
	@python -m ruff check .
	@python -m black --check .
	@python -m isort --check-only .

lint-frontend:
	@pnpm --prefix frontend run lint || true

fmt-backend:
	@python -m black .
	@python -m isort .

fmt-frontend:
	@pnpm --prefix frontend run format || true

# --- 🧪 CI/CD ---
ci:
	@echo "🤖 Ejecutando pipeline CI mínima..."
	@pytest -q --maxfail=1 --disable-warnings -q

# --- 🔄 VERIFICACIÓN COMPLETA ---
verify-all:
	@echo "🔄 Verificando BullBearBroker (lint + backend + frontend)..."
	@make lint
	@make test
	@make test-frontend
	@echo "✅ Verificación completa finalizada."

# --- 🧹 LIMPIEZA ---
clean:
	@echo "🧹 Limpiando cachés y artefactos..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .mypy_cache

# QA: corre la matriz de backend (3 combinaciones A/B/C)
qa-backend:
	# A) Staging + sin autocreate + AI decorado OFF
	docker exec \
	  -e PYTHONHASHSEED=1 \
	  -e PYTEST_ADDOPTS="--maxfail=1 -q" \
	  -e BB_TEST_SEED=1 \
	  -e BULLBEAR_AI_DECORATE=0 \
	  -e BULLBEAR_SKIP_AUTOCREATE=1 \
	  bullbear_api bash -lc 'pytest -q'
	# B) Local + autocreate ON + AI por defecto
	docker exec \
	  -e PYTHONHASHSEED=1 \
	  -e PYTEST_ADDOPTS="--maxfail=1 -q" \
	  -e BB_TEST_SEED=1 \
	  -e APP_ENV=local \
	  -e BULLBEAR_SKIP_AUTOCREATE=0 \
	  bullbear_api bash -lc 'pytest -q'
	# C) Staging + AI explícitamente ON
	docker exec \
	  -e PYTHONHASHSEED=1 \
	  -e PYTEST_ADDOPTS="--maxfail=1 -q" \
	  -e BB_TEST_SEED=1 \
	  -e APP_ENV=staging \
	  -e BULLBEAR_AI_DECORATE=1 \
	  -e BULLBEAR_SKIP_AUTOCREATE=1 \
	  bullbear_api bash -lc 'pytest -q'

# QA: cobertura con .coveragerc
qa-backend-cov:
	docker exec bullbear_api bash -lc 'pytest --cov=backend --cov-config=.coveragerc --cov-report=term-missing --cov-report=xml -q'

# QA: frontend (lint + tests con coverage)
qa-frontend:
	# QA: asegurar pnpm habilitado (Corepack)
	command -v pnpm >/dev/null 2>&1 || (corepack enable && corepack prepare pnpm@latest --activate)
	pnpm -C frontend install --frozen-lockfile
	pnpm -C frontend run lint
	pnpm -C frontend exec jest --config jest.config.dev.cjs --coverage --passWithNoTests

# QA: todo
# QA: deprecated qa-full aggregator replaced by unified qa-full recipe below
# qa-full: qa-backend qa-backend-cov qa-frontend

# QA: reconstruye contenedores (idempotente)
qa-rebuild:
	docker compose down -v
	docker compose up -d --build

# QA: smoke de base de datos
qa-db-smoke:
	docker exec bullbear_api bash -lc 'python -c "import sqlalchemy as sa; from backend.utils.config import Config; engine = sa.create_engine(Config.DATABASE_URL, pool_pre_ping=True); conn = engine.connect(); print(\"db_ok\", conn.execute(sa.text(\"select 1\")).scalar()); conn.close()"'

# QA: migra usando el Postgres local del compose (evita Supabase/SSL)
qa-migrate-local:
	docker exec \
	  -e APP_ENV=staging \
	  -e DATABASE_URL=postgresql+psycopg://$$(BASIC_AUTH_USER):$$(BASIC_AUTH_PASS)@db:5432/postgres \
	  bullbear_api bash -lc 'alembic upgrade head'

# QA: smoke DB con Postgres local
qa-db-smoke-local:
	docker exec \
	  -e DATABASE_URL=postgresql+psycopg://$$(BASIC_AUTH_USER):$$(BASIC_AUTH_PASS)@db:5432/postgres \
	  bullbear_api bash -lc 'python -c "import os, sqlalchemy as sa; url=os.environ[\"DATABASE_URL\"]; engine=sa.create_engine(url, pool_pre_ping=True); conn = engine.connect(); print(\"db_ok\", conn.execute(sa.text(\"select 1\")).scalar()); conn.close()"'

# QA: 4 workers + loadfile reduce contención y evita locks en cachés/modelos
qa-backend-parallel:
	docker exec bullbear_api bash -lc 'pytest -n 4 --dist=loadfile -m "not slow and not rate_limit and not e2e" -q'

# QA: corre en serie lo sensible
qa-backend-serial:
	docker exec bullbear_api bash -lc 'pytest -m "slow or rate_limit or e2e" -q'

# QA: Playwright targets tolerantes en local
test-e2e:
	@pnpm --prefix frontend exec playwright test --config=playwright.config.ts || true

test-e2e-report:
	@pnpm --prefix frontend exec playwright show-report || true

.PHONY: qa-full
qa-full:
	@bash scripts/qa_full_check.sh
