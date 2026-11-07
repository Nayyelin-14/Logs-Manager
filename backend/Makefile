# Local Development Makefile for FastAPI Backend
# The root Makefile is the canonical workflow (make up, make seed, make test).
# This file contains backend-only convenience targets.

.PHONY: help install install-dev test verify-schema test-connectivity run-dev lint typecheck

# Default target
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

# Install dependencies
install:
	pip install -r requirements.txt

# Install package in development mode (allows importing 'app' from anywhere)
install-dev:
	pip install -e .

# Test connectivity to existing Neon/Redis
test-connectivity:
	python scripts/test_connectivity.py

# Verify schema against Neon (READ-ONLY)
verify-schema:
	python scripts/verify_schema.py

# Run all tests
test:
	pytest tests/ -v

# Run model tests only
test-models:
	pytest tests/test_models.py -v

# Start development server (port 4501 to avoid conflicting with the Docker appliance on 4500)
run-dev:
	uvicorn app.main:app --host 0.0.0.0 --port 4501 --reload

# Linting
lint:
	ruff check app/ tests/ scripts/

# Type checking
typecheck:
	mypy app/

# Formatting
format:
	black app/ tests/ scripts/
	ruff check --fix app/ tests/ scripts/