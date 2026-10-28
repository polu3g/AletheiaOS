.DEFAULT_GOAL := help

# ── Variables ──────────────────────────────────────────────────────────────────
# Use the Python that has the packages. Override with: make dev PYTHON=/path/to/python
PYTHON     := $(shell command -v python3.15 2>/dev/null || command -v /usr/local/bin/python3 2>/dev/null || echo python3)
PIP        := $(PYTHON) -m pip
UVICORN    := $(PYTHON) -m uvicorn
APP        := app.main:app
PORT       := 8000

.PHONY: help install dev test test-cov lint format clean \
        docker-build docker-up docker-down logs shell

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────────

install:  ## Install all Python dependencies
	$(PIP) install -r requirements.txt

install-dev:  ## Install with dev extras (ruff, mypy)
	$(PIP) install -r requirements.txt ruff mypy

# ── Development ────────────────────────────────────────────────────────────────

dev:  ## Start dev server with hot-reload on port 8000
	$(UVICORN) $(APP) --reload --host 0.0.0.0 --port $(PORT)

dev-debug:  ## Start dev server in debug mode
	DEBUG=true $(UVICORN) $(APP) --reload --host 0.0.0.0 --port $(PORT) --log-level debug

# ── Testing ────────────────────────────────────────────────────────────────────

test:  ## Run all tests
	pytest tests/ -v --tb=short

test-cov:  ## Run tests with HTML coverage report
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing

test-unit:  ## Run unit tests only (no API tests)
	pytest tests/test_engine.py tests/test_memory.py tests/test_reasoning.py -v

test-api:  ## Run API integration tests only
	pytest tests/test_api.py -v

# ── Code Quality ───────────────────────────────────────────────────────────────

lint:  ## Lint with ruff
	ruff check app/ tests/

format:  ## Format code with ruff
	ruff format app/ tests/

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:  ## Remove bytecode, caches, and test artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	rm -rf .pytest_cache htmlcov .coverage aletheia.db data/rdf_store.ttl; true

# ── Docker ─────────────────────────────────────────────────────────────────────

docker-build:  ## Build the Docker image
	docker compose build

docker-up:  ## Start all services (app + rdf4j) in the background
	docker compose up -d

docker-down:  ## Stop and remove all containers
	docker compose down

logs:  ## Tail app container logs
	docker compose logs -f app

shell:  ## Open a shell inside the running app container
	docker compose exec app /bin/bash
