COMPOSE ?= docker compose

.PHONY: up down logs build clean test

up:
	$(COMPOSE) up -d

build:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f

test:
	python -m pytest backend/tests
	npm --prefix frontend test -- --watch=false
