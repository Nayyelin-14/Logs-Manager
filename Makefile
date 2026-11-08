SHELL := /bin/bash

REPO_ROOT := $(shell pwd)
BACKEND_DIR := $(REPO_ROOT)/backend
COMPOSE_LOCAL := docker compose -p lms_local -f docker-compose.yml
COMPOSE_VM := docker compose -p lms_vm -f docker-compose.vm.yml

TEST_DB_PORT ?= 55432
TEST_REDIS_PORT ?= 56379

.PHONY: help up down restart logs ps seed test lint validate demo reset maintenance verify env samples frontend-install frontend-check check-env check-files check compose-check test-deps backend-test backend-up backend-down backend-ps backend-shell backend-migrate saas-check saas-smoke set-password set-api-key

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
	@echo "  make check           check-env + check-files + saas-check + frontend-check"
	@echo "  make compose-check   Validate Docker Compose files parse"
	@echo "  make saas-check      Validate render.yaml and frontend/vercel.json"
	@echo "  make saas-smoke      Smoke test a deployed SaaS URL (SAAS_BACKEND_URL, SAAS_FRONTEND_URL)"
	@echo "  make set-password    Set a user password (IDENTIFIER=email-or-username PASSWORD=...)"
	@echo "  make set-api-key     Rotate a tenant ingestion key (TENANT=demoa [KEY=...])"
	@echo "  make test-deps       Start only db + redis for backend tests"

up: env
	$(COMPOSE_LOCAL) up -d --build

down:
	$(COMPOSE_LOCAL) down

restart:
	$(COMPOSE_LOCAL) restart

logs:
	$(COMPOSE_LOCAL) logs -f

ps:
	$(COMPOSE_LOCAL) ps

env:
	@test -f .env || cp .env.example .env
	@echo "Using .env (an existing file is never overwritten)"

seed: env
	$(COMPOSE_LOCAL) exec -T backend python scripts/seed_demo_data.py

seeds: seed

demo: env
	@python3 $(REPO_ROOT)/samples/simulator.py \
		--rate 20 --duration 15 --scenario bruteforce \
		--tenants demoA \
		--url http://localhost:4500 \
		--api-key "$${INGEST_API_KEY:-dev-ingest-key-change-me}" \
		--syslog-host 127.0.0.1 --syslog-port 514

backend-up: up
backend-down: down
backend-ps: ps
backend-shell:
	$(COMPOSE_LOCAL) exec backend sh

backend-test:
	@cd $(BACKEND_DIR) && TEST_DATABASE_URL="postgresql+asyncpg://logs:postgres_pass@localhost:$(TEST_DB_PORT)/logs_manager_test?sslmode=disable" TEST_REDIS_PORT=$(TEST_REDIS_PORT) ./.venv/bin/python -m pytest -q

test: backend-test

frontend-install:
	cd $(REPO_ROOT)/frontend && npm ci

frontend-check:
	cd $(REPO_ROOT)/frontend && npm run lint && npx tsc -b && npm run build

check-env:
	python3 $(REPO_ROOT)/scripts/check_env_sync.py

check-files:
	@bash $(REPO_ROOT)/scripts/check_file_sizes.sh

check: check-env check-files saas-check frontend-check

compose-check:
	docker compose -p lms_local -f docker-compose.yml config -q
	BACKEND_IMAGE=example/backend INGEST_IMAGE=example/ingest FRONTEND_IMAGE=example/frontend DOMAIN=example.com docker compose -p lms_vm -f docker-compose.vm.yml config -q

saas-check:
	@python3 $(REPO_ROOT)/scripts/check_saas_config.py

saas-smoke:
	@bash $(REPO_ROOT)/scripts/smoke_saas.sh "$${SAAS_BACKEND_URL:?set SAAS_BACKEND_URL}" "$${SAAS_FRONTEND_URL:-}"

set-password:
	@test -n "$$IDENTIFIER" -a -n "$$PASSWORD" || (echo "usage: make set-password IDENTIFIER=admin@demo.local PASSWORD=..."; exit 1)
	cd $(BACKEND_DIR) && .venv/bin/python3 scripts/set_password.py "$$IDENTIFIER" "$$PASSWORD"

set-api-key:
	@test -n "$$TENANT" || (echo "usage: make set-api-key TENANT=demoa [KEY=...]"; exit 1)
	cd $(BACKEND_DIR) && .venv/bin/python3 scripts/set_api_key.py "$$TENANT" "$${KEY:-}"

test-deps: env
	$(COMPOSE_LOCAL) up -d db redis

backend-migrate:
	@cd $(BACKEND_DIR) && .venv/bin/python -m alembic upgrade head

maintenance: env
	$(COMPOSE_LOCAL) exec -T backend python -m app.services.retention --days $${RETENTION_DAYS:-7}

demo-retention: env
	bash $(REPO_ROOT)/scripts/demo_retention.sh

reset: env
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

validate:
	@echo "Validating configuration..."
	@test -f docker-compose.yml && echo "Compose (local): OK" || (echo "Compose (local): MISSING"; exit 1)
	@test -f docker-compose.vm.yml && echo "Compose (VM): OK" || (echo "Compose (VM): MISSING"; exit 1)
	@test -f .env.example && echo ".env.example: OK" || (echo ".env.example: MISSING"; exit 1)
	@test -f $(BACKEND_DIR)/app/main.py && echo "FastAPI app: OK" || (echo "FastAPI app: MISSING"; exit 1)
	@test -f $(BACKEND_DIR)/scripts/seed_demo_data.py && echo "Seed script: OK" || (echo "Seed script: MISSING"; exit 1)
	@test -d $(REPO_ROOT)/ingest && echo "Ingest directory: OK" || (echo "Ingest dir: MISSING"; exit 1)
	@test -f $(REPO_ROOT)/samples/simulator.py && echo "Simulator: OK" || (echo "Simulator: MISSING"; exit 1)
	@echo "Validation complete"

lint:
	@bash $(REPO_ROOT)/scripts/check_file_sizes.sh
	@test -f docker-compose.yml && echo "Compose (local): OK" || (echo "Compose (local): MISSING"; exit 1)
	@test -f docker-compose.vm.yml && echo "Compose (VM): OK" || (echo "Compose (VM): MISSING"; exit 1)
	@test -f Caddyfile && echo "Caddyfile: OK" || (echo "Caddyfile: MISSING"; exit 1)

verify:
	@bash $(REPO_ROOT)/scripts/acceptance_check.sh

samples:
	@ls -la $(REPO_ROOT)/samples/