SHELL := /bin/bash

# Repo root (this Makefile lives at repo root)
REPO_ROOT := $(shell pwd)
BACKEND_DIR := $(REPO_ROOT)/backend-fastapi
COMPOSE_BASE := docker compose -f docker-compose.yml
COMPOSE := $(COMPOSE_BASE) -f docker-compose.appliance.yml
COMPOSE_SAAS := $(COMPOSE_BASE) -f docker-compose.saas.yml

# Test configuration - can be overridden via environment
TEST_DB_PORT ?= 55432
TEST_REDIS_PORT ?= 56379

.PHONY: help up down up-saas down-saas restart logs ps seed test lint validate demo reset maintenance verify env samples backend-test backend-up backend-down backend-ps backend-shell backend-test backend-migrate

# -----------------------
# Help
# -----------------------

help:
	@echo "Logs Manager - Fullstack assignment targets:"
	@echo ""
	@echo "  make up              Start Docker Compose stack (appliance mode)"
	@echo "  make up-saas         Start Docker Compose stack (SaaS mode, requires env vars)"
	@echo "  make down            Stop and remove Docker Compose stack"
	@echo "  make down-saas       Stop and remove SaaS Docker Compose stack"
	@echo "  make restart         Restart Docker Compose stack"
	@echo "  make logs            Follow container logs"
	@echo "  make ps              Show container status"
	@echo "  make env             Create .env from .env.example if missing"
	@echo "  make seed            Seed demo tenants, users, logs, alert rules"
	@echo "  make demo            Run bruteforce simulator to trigger alerts"
	@echo "  make test            Run backend pytest tests"
	@echo "  make lint            Run file size check + backend/frontend lint"
	@echo "  make validate        Validate configuration and code"
	@echo "  make maintenance     Run retention maintenance once"
	@echo "  make reset           Dev data reset (confirmation required, refuses Neon)"
	@echo "  make verify          Run acceptance checklist against running stack"
	@echo "  make backend-shell   Shell into backend container"

# -----------------------
# Docker Compose - Appliance mode
# -----------------------

up: env ## Start Docker Compose stack (appliance mode)
	$(COMPOSE) up -d --build

down: ## Stop and remove Docker Compose stack
	$(COMPOSE) down

restart: ## Restart Docker Compose stack
	$(COMPOSE) restart

logs: ## Follow container logs
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

# -----------------------
# Docker Compose - SaaS mode
# -----------------------

up-saas: env ## Start Docker Compose stack (SaaS mode)
	$(COMPOSE_SAAS) up -d --build

down-saas: ## Stop and remove SaaS Docker Compose stack
	$(COMPOSE_SAAS) down

# -----------------------
# Configuration
# -----------------------

env: ## Create .env from .env.example if missing
	@test -f .env || cp .env.example .env
	@echo "Using .env (an existing file is never overwritten)"

# -----------------------
# Seed data
# -----------------------

seed: env ## Seed demo tenants, users, logs, alert rules
	$(COMPOSE) exec -T backend python scripts/seed_demo_data.py

seeds: seed ## Alias for seed

# -----------------------
# Demo
# -----------------------

demo: env ## Run bruteforce simulator to trigger alerts (requires running stack)
	@python3 $(REPO_ROOT)/samples/simulator.py \
		--rate 20 --duration 15 --scenario bruteforce \
		--tenants demoA \
		--url http://localhost:4500 \
		--api-key "$${INGEST_API_KEY:-dev-ingest-key-change-me}" \
		--syslog-host 127.0.0.1 --syslog-port 514

# -----------------------
# Backend targets (aliases)
# -----------------------

backend-up: up
backend-down: down
backend-ps: ps
backend-shell: ## Shell into backend container
	$(COMPOSE) exec backend sh

backend-test: ## Run backend pytest tests (requires running stack or container exec)
	@cd $(BACKEND_DIR) && TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:$(TEST_DB_PORT)/logs_manager_test?sslmode=disable" TEST_REDIS_PORT=$(TEST_REDIS_PORT) ./.venv/bin/python -m pytest -q

test: backend-test ## Alias for backend-test

backend-migrate: ## Apply Alembic migrations
	@cd $(BACKEND_DIR) && .venv/bin/python -m alembic upgrade head

# -----------------------
# Maintenance
# -----------------------

maintenance: env ## Run retention maintenance once
	$(COMPOSE) exec -T backend python -m app.services.retention --days $${RETENTION_DAYS:-7}

# -----------------------
# Reset (dev only)
# -----------------------

reset: env ## Dev data reset (confirmation required; refuses Neon)
	@echo -n "This will destroy all data. Type 'yes' to continue: " && read ans && \
	if [ "$$ans" = "yes" ]; then \
		case "$$(grep DATABASE_URL .env 2>/dev/null | cut -d= -f2)" in \
			*neon*|*Neon*) echo "Refusing to reset Neon database."; exit 1 ;; \
		esac; \
		$(COMPOSE) down -v 2>/dev/null || true; \
		$(COMPOSE) up -d --build; \
		echo "Waiting for services..."; \
		sleep 10; \
		$(COMPOSE) exec -T backend python scripts/seed_demo_data.py; \
	else \
		echo "Reset cancelled."; \
	fi

# -----------------------
# Validation
# -----------------------

validate: ## Validate configuration and code
	@echo "Validating configuration..."
	@test -f docker-compose.yml && echo "Compose: OK" || (echo "Compose: MISSING"; exit 1)
	@test -f docker-compose.appliance.yml && echo "Compose (appliance): OK" || (echo "Compose appliance: MISSING"; exit 1)
	@test -f docker-compose.saas.yml && echo "Compose (saas): OK" || (echo "Compose saas: MISSING"; exit 1)
	@test -f .env.example && echo ".env.example: OK" || (echo ".env.example: MISSING"; exit 1)
	@test -f $(BACKEND_DIR)/app/main.py && echo "FastAPI app: OK" || (echo "FastAPI app: MISSING"; exit 1)
	@test -f $(BACKEND_DIR)/scripts/seed_demo_data.py && echo "Seed script: OK" || (echo "Seed script: MISSING"; exit 1)
	@test -d $(REPO_ROOT)/ingest && echo "Ingest directory: OK" || (echo "Ingest dir: MISSING"; exit 1)
	@test -f $(REPO_ROOT)/samples/simulator.py && echo "Simulator: OK" || (echo "Simulator: MISSING"; exit 1)
	@echo "Validation complete"

# -----------------------
# Lint
# -----------------------

lint: ## File size check + basic validation
	@bash $(REPO_ROOT)/scripts/check_file_sizes.sh
	@test -f docker-compose.yml && echo "Compose: OK" || (echo "Compose: MISSING"; exit 1)
	@test -f docker-compose.appliance.yml && echo "Compose (appliance): OK" || (echo "Compose appliance: MISSING"; exit 1)
	@test -f docker-compose.saas.yml && echo "Compose (saas): OK" || (echo "Compose saas: MISSING"; exit 1)
	@test -f Caddyfile && echo "Caddyfile: OK" || (echo "Caddyfile: MISSING"; exit 1)

# -----------------------
# Verify (acceptance checklist)
# -----------------------

verify: ## Run acceptance checklist against running stack
	@bash $(REPO_ROOT)/scripts/acceptance_check.sh

# -----------------------
# Samples
# -----------------------

samples: ## List sample files
	@ls -la $(REPO_ROOT)/samples/