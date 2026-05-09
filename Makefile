.PHONY: install dev db-up db-down db-reset lint typecheck test test-unit test-int test-contract fmt clean help

API_DIR := apps/api
COMPOSE := docker compose -f infra/docker-compose.yml

help:
	@echo "Common targets:"
	@echo "  install        Install Python deps via uv (in apps/api)"
	@echo "  dev            Run FastAPI dev server (reload, :8000)"
	@echo "  db-up          Start Postgres + pgvector via Docker Compose"
	@echo "  db-down        Stop Postgres"
	@echo "  db-reset       Stop Postgres and wipe its volume"
	@echo "  lint           Run ruff check + format check"
	@echo "  fmt            Run ruff format and auto-fix"
	@echo "  typecheck      Run pyright (strict)"
	@echo "  test           Run all tests"
	@echo "  test-unit      Run only unit tests"
	@echo "  test-int       Run only integration tests"
	@echo "  test-contract  Run only contract tests"
	@echo "  precommit      Install pre-commit hooks (one-time per clone)"
	@echo "  precommit-run  Run all pre-commit hooks against all files"
	@echo "  clean          Remove caches and build artefacts"

install:
	cd $(API_DIR) && uv sync --all-extras

dev:
	cd $(API_DIR) && uv run uvicorn cora.api.main:app --reload --host 0.0.0.0 --port 8000

db-up:
	$(COMPOSE) up -d postgres

db-down:
	$(COMPOSE) down

db-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d postgres

lint:
	cd $(API_DIR) && uv run ruff check src tests
	cd $(API_DIR) && uv run ruff format --check src tests

fmt:
	cd $(API_DIR) && uv run ruff check --fix src tests
	cd $(API_DIR) && uv run ruff format src tests

typecheck:
	cd $(API_DIR) && uv run pyright src tests

test:
	cd $(API_DIR) && uv run pytest

test-unit:
	cd $(API_DIR) && uv run pytest -m unit

test-int:
	cd $(API_DIR) && uv run pytest -m integration

test-contract:
	cd $(API_DIR) && uv run pytest -m contract

precommit:
	cd $(API_DIR) && uv run pre-commit install

precommit-run:
	cd $(API_DIR) && uv run pre-commit run --all-files

clean:
	cd $(API_DIR) && rm -rf .pytest_cache .ruff_cache .pyright_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
