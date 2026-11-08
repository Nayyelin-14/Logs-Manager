
.PHONY: help install install-dev test verify-schema test-connectivity run-dev lint typecheck

help:
	@echo "FastAPI Backend - Local Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          - Install Python dependencies"
	@echo "  make install-dev      - Install package in development mode (editable)"
	@echo ""
	@echo "Verification (read-only, safe for Neon):"
	@echo "  make test-connectivity - Test PostgreSQL/Redis connectivity"
	@echo "  make verify-schema     - Compare SQLAlchemy models with Neon schema (READ-ONLY)"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests"
	@echo "  make test-models       - Run model verification tests"
	@echo ""
	@echo "Development:"
	@echo "  make run-dev           - Start FastAPI dev server (uvicorn with reload)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run ruff linter"
	@echo "  make typecheck         - Run mypy type checker"
	@echo "  make format            - Run black formatter"

install:
	pip install -r requirements.txt

install-dev:
	pip install -e .

test-connectivity:
	python scripts/test_connectivity.py

verify-schema:
	python scripts/verify_schema.py

test:
	pytest tests/ -v

test-models:
	pytest tests/test_models.py -v

run-dev:
	uvicorn app.main:app --host 0.0.0.0 --port 4501 --reload

lint:
	ruff check app/ tests/ scripts/

typecheck:
	mypy app/

format:
	black app/ tests/ scripts/
	ruff check --fix app/ tests/ scripts/