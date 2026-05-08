# IDIntel Ghana — Developer Makefile
.PHONY: help dev-up dev-down migrate seed-dev test test-backend test-frontend \
        lint format clean build push logs shell-api keys-generate

# ============================================================
# Variables
# ============================================================
DOCKER_COMPOSE := docker compose
PYTHON := python3
SERVICE ?= api-gateway

# ============================================================
# Help
# ============================================================
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ============================================================
# Development Environment
# ============================================================
dev-up: ## Start all services
	@echo "Starting IDIntel Ghana development environment..."
	$(DOCKER_COMPOSE) up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo ""
	@echo "  API Gateway:   http://localhost:8000"
	@echo "  API Docs:      http://localhost:8000/docs"
	@echo "  Admin Portal:  http://localhost:3000"
	@echo "  Grafana:       http://localhost:3001"
	@echo "  RabbitMQ UI:   http://localhost:15672"
	@echo "  Neo4j:         http://localhost:7474"

dev-down: ## Stop all services
	$(DOCKER_COMPOSE) down

dev-restart: ## Restart a specific service (SERVICE=api-gateway)
	$(DOCKER_COMPOSE) restart $(SERVICE)

logs: ## Tail logs for a service (SERVICE=api-gateway)
	$(DOCKER_COMPOSE) logs -f $(SERVICE)

logs-all: ## Tail logs for all services
	$(DOCKER_COMPOSE) logs -f

# ============================================================
# Database
# ============================================================
migrate: ## Run database migrations
	$(DOCKER_COMPOSE) exec api-gateway alembic upgrade head

migrate-create: ## Create a new migration (MSG="description")
	$(DOCKER_COMPOSE) exec api-gateway alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## Roll back one migration
	$(DOCKER_COMPOSE) exec api-gateway alembic downgrade -1

seed-dev: ## Seed development database with test data
	$(DOCKER_COMPOSE) exec api-gateway python -m scripts.seed_dev_data

# ============================================================
# Testing
# ============================================================
test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	$(DOCKER_COMPOSE) exec api-gateway pytest backend/tests/ -v --tb=short

test-frontend: ## Run frontend tests
	cd frontend && npm test

test-coverage: ## Run backend tests with coverage report
	$(DOCKER_COMPOSE) exec api-gateway pytest backend/tests/ --cov=backend \
		--cov-report=html --cov-report=term-missing

# ============================================================
# Code Quality
# ============================================================
lint: ## Run all linters
	@echo "Linting Python..."
	ruff check backend/
	@echo "Linting TypeScript..."
	cd frontend && npm run lint

format: ## Auto-format all code
	ruff format backend/
	cd frontend && npx prettier --write src/

type-check: ## Run type checkers
	mypy backend/ --ignore-missing-imports
	cd frontend && npx tsc --noEmit

# ============================================================
# Security
# ============================================================
security-scan: ## Run security scans
	bandit -r backend/ -ll
	cd frontend && npx audit-ci --high

# ============================================================
# Key Generation (Development)
# ============================================================
keys-generate: ## Generate JWT signing keys for development
	@mkdir -p keys
	@openssl genrsa -out keys/private_key.pem 4096
	@openssl rsa -in keys/private_key.pem -pubout -out keys/public_key.pem
	@echo "JWT keys generated in ./keys/"
	@echo "WARNING: Development keys only — use HSM-backed keys in production"

# ============================================================
# Build
# ============================================================
build: ## Build all Docker images
	$(DOCKER_COMPOSE) build

build-service: ## Build a specific service (SERVICE=api-gateway)
	$(DOCKER_COMPOSE) build $(SERVICE)

# ============================================================
# ML Models
# ============================================================
train-model: ## Train fraud detection model (DATA=path/to/data.parquet)
	$(PYTHON) -m ml.fraud_detection.trainer --data-path $(DATA)

# ============================================================
# Utilities
# ============================================================
shell-api: ## Open a shell in the API gateway container
	$(DOCKER_COMPOSE) exec api-gateway /bin/bash

ps: ## Show running service status
	$(DOCKER_COMPOSE) ps

clean: ## Stop services and remove volumes (WARNING: deletes all data)
	@echo "WARNING: This will delete all development data. Press Ctrl+C to cancel."
	@sleep 5
	$(DOCKER_COMPOSE) down -v
	@echo "All services stopped and data cleared."
