COMPOSE ?= docker compose
ENV_FILE ?= .env.local

.PHONY: up up-local up-supabase down down-v logs build clean test up-staging down-staging migrate

up:
	ENV_FILE=$(ENV_FILE) $(COMPOSE) up -d

up-local:
	ENV_FILE=.env.local $(COMPOSE) up -d

up-supabase:
	ENV_FILE=.env.supabase $(COMPOSE) up -d

up-staging:
	APP_ENV=staging ENV_FILE=$(ENV_FILE) $(COMPOSE) --profile staging up -d

build:
	ENV_FILE=$(ENV_FILE) $(COMPOSE) up --build

down:
	ENV_FILE=$(ENV_FILE) $(COMPOSE) down

down-v:
	ENV_FILE=$(ENV_FILE) $(COMPOSE) down -v

down-staging:
	APP_ENV=staging ENV_FILE=$(ENV_FILE) $(COMPOSE) --profile staging down

clean:
	ENV_FILE=$(ENV_FILE) $(COMPOSE) down -v --remove-orphans

logs:
	ENV_FILE=$(ENV_FILE) $(COMPOSE) logs -f

migrate:
	ENV_FILE=$(ENV_FILE) bash -c 'set -a; if [ -f "$$ENV_FILE" ]; then . "$$ENV_FILE"; fi; alembic upgrade head'

test:
	python -m pytest backend/tests
	npm --prefix frontend test -- --watch=false
