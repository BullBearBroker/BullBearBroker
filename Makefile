COMPOSE ?= docker compose

.PHONY: up build down clean logs

up:
	$(COMPOSE) up

build:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f
