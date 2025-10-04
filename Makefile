.PHONY: venv dev test lint fmt migrate up down build run ci
venv:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
dev:
	docker compose up --build
test:
	pytest -q
lint:
	pre-commit run --all-files || true
fmt:
	black . && ruff --fix . && isort .
migrate:
	alembic upgrade head
build:
	docker build -t bullbear:local .
run:
	docker run --rm -p 8000:8000 bullbear:local
ci:
	pytest -q --maxfail=1 --disable-warnings -q
