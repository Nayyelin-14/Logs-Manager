SHELL := /bin/bash

.PHONY: help up down restart logs ps seed test test-backend clean docs architecture seeds samples validate backend-up backend-down backend-ps backend-test backend-migrate backend-shell

# -----------------------
# Top-level targets
# -----------------------

help:
	@echo "Logs Manager - Fullstack assignment targets:"
	@echo ""
	@echo "  make up              Start Docker Compose stack (FastAPI appliance mode)"
	@echo "  make down            Stop and remove Docker Compose stack"
	@echo "  make logs            Follow container logs"
	@echo "  make ps              Show container status"
	@echo "  make seed            Seed demo data (tenants, users, logs, alert rule)"
	@echo "  make test            Run backend pytest tests"
	@echo "  make validate        Validate configuration and code"

# -----------------------
# FastAPI Docker targets (canonical)
# -----------------------

up: ## Start Docker Compose stack (FastAPI appliance mode)
	@cd backend-fastapi && docker compose up -d --build

down: ## Stop and remove Docker Compose stack
	@cd backend-fastapi && docker compose down

restart: ## Restart Docker Compose stack
	@cd backend-fastapi && docker compose restart

logs: ## Follow container logs
	@cd backend-fastapi && docker compose logs -f

ps: ## Show container status
	@cd backend-fastapi && docker compose ps

# -----------------------
# Backend-fastapi targets (alias for clarity)
# -----------------------

backend-up: ## Start just the backend-fastapi services (postgres+redis+backend)
	@cd backend-fastapi && docker compose up -d --build

backend-down: ## Stop backend-fastapi services
	@cd backend-fastapi && docker compose down

backend-ps: ## Show backend-fastapi container status
	@cd backend-fastapi && docker compose ps

backend-test: ## Run backend pytest tests
	@cd backend-fastapi && ./.venv/bin/python -m pytest -q

test: backend-test ## Alias for backend-test

backend-migrate: ## Apply Alembic migrations inside backend-fastapi container
	@cd backend-fastapi && source .venv/bin/activate && alembic upgrade head

backend-shell: ## Shell into backend-fastapi container
	@cd backend-fastapi && docker compose exec backend sh

# -----------------------
# Configuration
# -----------------------

env: ## Create backend-fastapi/.env from its template if it doesn't exist
	@test -f backend-fastapi/.env || cp backend-fastapi/.env.example backend-fastapi/.env
	@echo "Using backend-fastapi/.env (an existing file is never overwritten)"

# -----------------------
# Seed data
# -----------------------

seed: ## Seed demo tenants, users, logs, and an alert rule (uses Docker database)
	@cd backend-fastapi && docker compose exec -T backend python scripts/seed_demo_data.py

seeds: seed ## Alias for seed target

# -----------------------
# Samples
# -----------------------

samples: ## Copy/verify sample log files and scripts
	@echo "Samples directory already present at samples/"

# -----------------------
# Validation
# -----------------------

validate: ## Validate configuration and code
	@echo "Validating configuration..."
	@test -f backend-fastapi/app/main.py && echo "FastAPI app exists" || (echo "FASTAPI MISSING"; exit 1)
	@test -f backend-fastapi/migrations/versions/a1b2c3d4e5f6_fresh_baseline.py && echo "Alembic migration exists" || (echo "MIGRATION MISSING"; exit 1)
	@test -f backend-fastapi/scripts/seed_demo_data.py && echo "Seed script exists" || (echo "SEED SCRIPT MISSING"; exit 1)
	@test -f backend-fastapi/docker-compose.yml && echo "Compose file exists" || (echo "COMPOSE FILE MISSING"; exit 1)
	@test -f backend-fastapi/.env.example && echo "Env template exists" || (echo "ENV TEMPLATE MISSING"; exit 1)
	@echo "Validation complete"

# -----------------------
# Documentation
# -----------------------

docs: ## Generate documentation files
	@echo "Documentation targets should be run individually:"
	@echo "  make docs.architecture - Generate architecture.md"
	@echo "  make docs.setup-appliance - Generate setup_appliance.md"
	@echo "  make docs.setup-saas - Generate setup_saas.md"

docs.architecture: ## Generate /docs/architecture.md
	@echo "Creating /docs/architecture.md ..."
	@mkdir -p /docs
	@printf '# Architecture Documentation\n\nTODO: Add architecture documentation here.\n' > /docs/architecture.md
	@echo "Done. Edit /docs/architecture.md as needed."

docs.setup-appliance: ## Generate /docs/setup_appliance.md
	@echo "Creating /docs/setup_appliance.md ..."
	@mkdir -p /docs
	@printf '# Appliance Setup Guide\n\nTODO: Add appliance setup instructions here.\n' > /docs/setup_appliance.md
	@echo "Done. Edit /docs/setup_appliance.md as needed."

docs.setup-saas: ## Generate /docs/setup_saas.md
	@echo "Creating /docs/setup_saas.md ..."
	@mkdir -p /docs
	@printf '# SaaS Setup Guide\n\nTODO: Add SaaS setup instructions here.\n' > /docs/setup_saas.md
	@echo "Done. Edit /docs/setup_saas.md as needed."
