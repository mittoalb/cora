.PHONY: install dev db-up db-down db-reset lint typecheck test test-unit test-int test-contract fmt clean help \
        migrate-status migrate-apply migrate-new migrate-hash precommit precommit-run \
        arch-check arch-show

API_DIR := apps/api
COMPOSE := docker compose -f infra/docker-compose.yml
ATLAS_DIR := infra/atlas
LOCAL_DB_URL ?= postgres://cora:cora@localhost:5432/cora?sslmode=disable

help:
	@echo "Common targets:"
	@echo "  install         Install Python deps via uv (in apps/api)"
	@echo "  dev             Run FastAPI dev server (reload, :8000)"
	@echo "  db-up           Start Postgres + pgvector via Docker Compose"
	@echo "  db-down         Stop Postgres"
	@echo "  db-reset        Stop Postgres and wipe its volume"
	@echo "  migrate-status  Show pending migrations against local DB"
	@echo "  migrate-apply   Apply pending migrations to local DB"
	@echo "  migrate-new     Generate a new migration skeleton (name=<short_name>)"
	@echo "  migrate-hash    Recompute atlas.sum after editing migrations by hand"
	@echo "  lint            Run ruff check + format check"
	@echo "  fmt             Run ruff format and auto-fix"
	@echo "  typecheck       Run pyright (strict)"
	@echo "  test            Run all tests"
	@echo "  test-unit       Run only unit tests"
	@echo "  test-int        Run only integration tests"
	@echo "  test-contract   Run only contract tests"
	@echo "  arch-check      Tach dependency contract + architecture fitness-function tests"
	@echo "  arch-show       Open the dependency graph (tach show)"
	@echo "  precommit       Install pre-commit hooks (one-time per clone)"
	@echo "  precommit-run   Run all pre-commit hooks against all files"
	@echo "  clean           Remove caches and build artefacts"

install:
	cd $(API_DIR) && uv sync --all-extras

dev: db-up
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

arch-check:
	cd $(API_DIR) && uv run tach check
	cd $(API_DIR) && uv run pytest tests/architecture

arch-show:
	cd $(API_DIR) && uv run tach show

precommit:
	cd $(API_DIR) && uv run pre-commit install

precommit-run:
	cd $(API_DIR) && uv run pre-commit run --all-files

migrate-status:
	cd $(ATLAS_DIR) && DATABASE_URL=$(LOCAL_DB_URL) atlas migrate status --env local

migrate-apply:
	cd $(ATLAS_DIR) && DATABASE_URL=$(LOCAL_DB_URL) atlas migrate apply --env local

migrate-new:
	@if [ -z "$(name)" ]; then echo "Usage: make migrate-new name=add_foo"; exit 1; fi
	cd $(ATLAS_DIR) && DATABASE_URL=$(LOCAL_DB_URL) atlas migrate new $(name)

migrate-hash:
	cd $(ATLAS_DIR) && atlas migrate hash

# `atlas migrate lint` was moved behind atlas-cloud login in v0.38; the
# project deliberately skips that path. CI runs a narrow grep-based
# safety scan on new migrations (see .github/workflows/ci.yml). Locally,
# read your migration carefully and `make migrate-apply` against a
# scratch DB before merging — that catches the same class of issues
# `lint` would flag (data loss, locking-prone DDL).

clean:
	cd $(API_DIR) && rm -rf .pytest_cache .ruff_cache .pyright_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
