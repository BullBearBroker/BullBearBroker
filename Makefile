COMPOSE ?= docker compose

.PHONY: up down logs build clean test up-staging down-staging

up:
        $(COMPOSE) up -d

up-staging:
        APP_ENV=staging $(COMPOSE) --profile staging up -d

build:
	$(COMPOSE) up --build

down:
        $(COMPOSE) down

down-staging:
        $(COMPOSE) --profile staging down

clean:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f

test:
	python -m pytest backend/tests
	npm --prefix frontend test -- --watch=false
