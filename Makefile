SHELL := /bin/bash

# Repo root (this Makefile lives at repo root)
REPO_ROOT := $(shell pwd)
BACKEND_DIR := $(REPO_ROOT)/backend-fastapi
COMPOSE_LOCAL := docker compose -p lms_local -f docker-compose.yml
COMPOSE_VM := docker compose -p lms_vm -f docker-compose.vm.yml

# Test configuration - can be overridden via environment
TEST_DB_PORT ?= 55432
TEST_REDIS_PORT ?= 56379

.PHONY: help up down restart logs ps seed test lint validate demo reset maintenance verify env samples frontend-install frontend-check check-env check-files check compose-check test-deps backend-test backend-up backend-down backend-ps backend-shell backend-migrate

# -----------------------
# Help
# -----------------------

help:
	@echo "Logs Manager - Fullstack assignment targets:"
	@echo ""
	@echo "  make up              Start local Docker Compose stack (docker-compose.yml, project: lms_local)"
	@echo "  make down            Stop and remove local Docker Compose stack"
	@echo "  make restart         Restart local Docker Compose stack"
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
	@echo "  make frontend-install  Install frontend dependencies (npm ci)"
	@echo "  make frontend-check  Frontend lint + typecheck + production build"
	@echo "  make check-env       Environment sync check (example files only; safe for CI)"
	@echo "  make check-files     File size and configuration validation"
	@echo "  make check           check-env + check-files + frontend-check"
	@echo "  make compose-check   Validate Docker Compose files parse"
	@echo "  make test-deps       Start only db + redis for backend tests"

# -----------------------
# Docker Compose - Appliance mode
# -----------------------

up: env ## Start local Docker Compose stack (docker-compose.yml, project: lms_local)
	$(COMPOSE_LOCAL) up -d --build

down: ## Stop and remove local Docker Compose stack
	$(COMPOSE_LOCAL) down

restart: ## Restart local Docker Compose stack
	$(COMPOSE_LOCAL) restart

logs: ## Follow container logs
	$(COMPOSE_LOCAL) logs -f

ps: ## Show container status
	$(COMPOSE_LOCAL) ps

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
	$(COMPOSE_LOCAL) exec -T backend python scripts/seed_demo_data.py

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
	$(COMPOSE_LOCAL) exec backend sh

backend-test: ## Run backend pytest tests (requires running stack or container exec)
	@cd $(BACKEND_DIR) && TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:$(TEST_DB_PORT)/logs_manager_test?sslmode=disable" TEST_REDIS_PORT=$(TEST_REDIS_PORT) ./.venv/bin/python -m pytest -q

test: backend-test ## Alias for backend-test

frontend-install: ## Install frontend dependencies
	cd $(REPO_ROOT)/frontend/lms && npm ci

frontend-check: ## Frontend lint + typecheck + production build
	cd $(REPO_ROOT)/frontend/lms && npm run lint && npx tsc -b && npm run build

check-env: ## Environment sync check (example files only; safe for CI)
	python3 $(REPO_ROOT)/scripts/check_env_sync.py

check-files: ## File size and configuration validation
	@bash $(REPO_ROOT)/scripts/check_file_sizes.sh

check: check-env check-files frontend-check ## Run safe acceptance checks (no local .env.local read)

compose-check: ## Validate Docker Compose files parse
	docker compose -p lms_local -f docker-compose.yml config -q
	DOMAIN=example.com docker compose -p lms_vm -f docker-compose.vm.yml config -q

test-deps: env ## Start only db + redis for backend tests
	$(COMPOSE_LOCAL) up -d db redis

backend-migrate: ## Apply Alembic migrations
	@cd $(BACKEND_DIR) && .venv/bin/python -m alembic upgrade head

# -----------------------
# Maintenance
# -----------------------

maintenance: env ## Run retention maintenance once
	$(COMPOSE_LOCAL) exec -T backend python -m app.services.retention --days $${RETENTION_DAYS:-7}

demo-retention: env ## Demonstrate retention: 8-day-old purged, 6-day-old kept
	bash $(REPO_ROOT)/scripts/demo_retention.sh

# -----------------------
# Reset (dev only)
# -----------------------

reset: env ## Dev data reset (confirmation required; refuses Neon)
	@echo -n "This will destroy all data. Type 'yes' to continue: " && read ans && \
	if [ "$$ans" = "yes" ]; then \
		case "$$(grep DATABASE_URL .env 2>/dev/null | cut -d= -f2)" in \
			*neon*|*Neon*) echo "Refusing to reset Neon database."; exit 1 ;; \
		esac; \
		$(COMPOSE_LOCAL) down -v 2>/dev/null || true; \
		$(COMPOSE_LOCAL) up -d --build; \
		echo "Waiting for services..."; \
		sleep 10; \
		$(COMPOSE_LOCAL) exec -T backend python scripts/seed_demo_data.py; \
	else \
		echo "Reset cancelled."; \
	fi

# -----------------------
# Validation
# -----------------------

validate: ## Validate configuration and code
	@echo "Validating configuration..."
	@test -f docker-compose.yml && echo "Compose (local): OK" || (echo "Compose (local): MISSING"; exit 1)
	@test -f docker-compose.vm.yml && echo "Compose (VM): OK" || (echo "Compose (VM): MISSING"; exit 1)
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
	@test -f docker-compose.yml && echo "Compose (local): OK" || (echo "Compose (local): MISSING"; exit 1)
	@test -f docker-compose.vm.yml && echo "Compose (VM): OK" || (echo "Compose (VM): MISSING"; exit 1)
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