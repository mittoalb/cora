.PHONY: install dev db-up db-down db-reset lint typecheck test test-unit test-int test-contract \
        test-coverage diff-coverage fmt clean help \
        migrate-status migrate-apply migrate-new migrate-hash precommit precommit-run \
        arch-check arch-show docs-stage docs-build docs-serve openapi-snapshot

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
	@echo "  test-coverage   Run all tests with coverage report (term + html + xml)"
	@echo "  diff-coverage   Run diff-cover against origin/main (fails if patch <90%)"
	@echo "  arch-check      Tach dependency contract + architecture fitness-function tests"
	@echo "  arch-show       Open the dependency graph (tach show)"
	@echo "  openapi-snapshot Regenerate apps/api/openapi.json from create_app()"
	@echo "  precommit       Install pre-commit hooks (one-time per clone)"
	@echo "  precommit-run   Run all pre-commit hooks against all files"
	@echo "  docs-stage      Stage README + CONTRIBUTING into docs/ (link rewrites for site)"
	@echo "  docs-build      Stage + build the static site into ./site"
	@echo "  docs-serve      Stage + serve the docs site locally on :8001"
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

# pytest-xdist with `--dist=worksteal -n 4`: worksteal is the
# scheduler-of-choice for mixed-duration suites (50ms unit alongside
# 200ms+ integration). Worker count is empirically tuned: on the 8-core
# dev Mac, `-n 4` finished coverage in 9:08 while `-n 8` took 13:10
# *and* tripped a flaky asyncio concurrency test — the suite is
# I/O-bound on per-worker Postgres, so 8 workers oversubscribe Docker
# and asyncpg. `-n 4` also matches ubuntu-latest CI's 4-core runner
# exactly. Each worker brings up its own Postgres container (see
# tests/conftest.py); the per-test template-DB clone parallelizes
# cleanly. Raise the cap empirically if a future I/O speedup (tmpfs
# Docker volume, faster runner class) unblocks worker scaling.
#
# Kept out of `[tool.pytest.ini_options].addopts` so ad-hoc single-file
# runs (`uv run pytest tests/unit/foo.py`) stay sequential and avoid
# worker-spawn overhead. Make targets opt in.
PYTEST_PARALLEL := -n 4 --dist=worksteal

test:
	cd $(API_DIR) && uv run pytest $(PYTEST_PARALLEL)

test-unit:
	cd $(API_DIR) && uv run pytest $(PYTEST_PARALLEL) -m unit

test-int:
	cd $(API_DIR) && uv run pytest $(PYTEST_PARALLEL) -m integration

test-contract:
	cd $(API_DIR) && uv run pytest $(PYTEST_PARALLEL) -m contract

test-coverage:
	cd $(API_DIR) && uv run pytest $(PYTEST_PARALLEL) --cov --cov-report=term-missing --cov-report=html --cov-report=xml

diff-coverage:
	cd $(API_DIR) && uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=90

arch-check:
	cd $(API_DIR) && uv run tach check
	cd $(API_DIR) && uv run pytest tests/architecture

arch-show:
	cd $(API_DIR) && uv run tach show

# Regenerate the committed OpenAPI snapshot after intentional API surface
# changes. The drift test (tests/architecture/test_openapi_drift.py) fails
# until this is run and the diff is reviewed in the PR.
openapi-snapshot:
	cd $(API_DIR) && APP_ENV=test uv run python -c "import json; from cora.api.main import create_app; \
		f = open('openapi.json', 'w'); json.dump(create_app().openapi(), f, indent=2, sort_keys=True); f.write('\n'); f.close()"

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

# Docs site (mkdocs-material) — published to xmap.github.io/cora/ via
# .github/workflows/docs.yml on every push to main. Locally, install
# mkdocs-material once with: pip install --user mkdocs-material==9.5.49

docs-stage:
	python3 scripts/stage_docs.py

docs-build: docs-stage
	mkdocs build --strict

docs-serve: docs-stage
	mkdocs serve -a localhost:8001

clean:
	cd $(API_DIR) && rm -rf .pytest_cache .ruff_cache .pyright_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf site docs/index.md docs/contributing.md
