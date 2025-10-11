# ================================
# 🚀 BullBearBroker Makefile Final
# ================================

.PHONY: venv dev test lint fmt migrate up-local up-staging down build run ci verify-all clean

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

run:
	@echo "🚀 Ejecutando contenedor local en puerto 8000..."
	docker run --rm -p 8000:8000 bullbear:local

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
	@echo "🧪 Ejecutando tests del frontend (Jest)..."
	@pnpm --prefix frontend run test -- --coverage  # CODEx: unificamos ejecución de Jest con pnpm

test-all:
	@echo "🔄 Ejecutando validaciones completas (lint + backend + frontend)..."
	@pre-commit run --all-files || true  # CODEx: ejecutar hooks de forma no bloqueante
	@pytest backend/tests -vv  # CODEx: validar suite de backend en modo detallado
	@pnpm --prefix frontend run test:dev  # CODEx: ejecutar suite unitaria/integración del frontend sin UI

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

qa-full:
	@bash scripts/qa_full.sh
