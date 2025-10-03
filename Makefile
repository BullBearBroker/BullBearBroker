SHELL := /bin/bash

.PHONY: setup dev-venv lint format typecheck test cov postman openapi

setup:
	python -m pip install -r backend/requirements.txt
	python -m pip install -r backend/requirements-dev.txt || true
	pre-commit install || true

dev-venv: setup

lint:
	@command -v pre-commit >/dev/null 2>&1 || python -m pip install pre-commit -q
	pre-commit run --all-files || true
	ruff check .

format:
	black .
	isort .

typecheck:
	mypy backend || true

test:
	pytest backend -q

cov:
	pytest --cov=backend --cov-report=term-missing backend

openapi:
	python scripts/generate_postman.py --export-openapi

postman:
	python scripts/generate_postman.py
