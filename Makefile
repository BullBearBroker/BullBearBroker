COMPOSE ?= docker compose

.PHONY: up up-local up-supabase up-staging down down-v down-staging clean logs migrate test test-backend test-frontend check-all

up: up-local

up-local:
	$(COMPOSE) --env-file .env.local up -d --build

up-supabase:
	$(COMPOSE) --env-file .env.supabase up -d --build

up-staging:
	APP_ENV=staging $(COMPOSE) --env-file .env.local --profile staging up -d --build

down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v

down-staging:
	APP_ENV=staging $(COMPOSE) --profile staging down

clean:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f --tail=200

migrate:
	$(COMPOSE) exec backend alembic upgrade head

test-backend:
	$(COMPOSE) exec backend pytest backend/tests -q

test-frontend:
	NEXT_PUBLIC_API_URL=http://localhost:8000 npm --prefix frontend run test:dev

test: test-backend test-frontend

check-all: migrate test-backend test-frontend
