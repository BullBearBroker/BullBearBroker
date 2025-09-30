COMPOSE ?= docker compose

.PHONY: up up-local up-supabase up-staging down down-v down-staging clean logs logs-local logs-supabase logs-staging migrate test test-backend test-frontend check-all

# ========================
# 🚀 UP (Levantar servicios)
# ========================
up: up-local

up-local:
	$(COMPOSE) --env-file .env.local up -d --build

up-supabase:
	$(COMPOSE) --env-file .env.supabase up -d --build

up-staging:
	APP_ENV=staging $(COMPOSE) --env-file .env.local --profile staging up -d --build

# ========================
# 🛑 DOWN (Apagar servicios)
# ========================
down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v

down-staging:
	APP_ENV=staging $(COMPOSE) --profile staging down

clean:
	$(COMPOSE) down -v --remove-orphans

# ========================
# 📜 LOGS (separados por entorno)
# ========================
logs:
	$(COMPOSE) logs -f --tail=200

logs-local:
	$(COMPOSE) --env-file .env.local --profile default logs -f --tail=200

logs-supabase:
	$(COMPOSE) --env-file .env.supabase --profile default logs -f --tail=200

logs-staging:
	APP_ENV=staging $(COMPOSE) --env-file .env.supabase --profile staging logs -f --tail=200

# ========================
# 🛠️ Migraciones
# ========================
migrate:
	$(COMPOSE) exec backend alembic upgrade head

# ========================
# 🧪 TESTS
# ========================
test-backend:
	$(COMPOSE) exec backend pytest backend/tests -q

test-frontend:
	NEXT_PUBLIC_API_URL=http://localhost:8000 npm --prefix frontend run test:dev

test: test-backend test-frontend

check-all: migrate test-backend test-frontend
