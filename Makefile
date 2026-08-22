.PHONY: install install-dev test test-all test-python test-unit test-integration test-api lint fmt clean example api-dev api-serve web-install web-dev web-build web-test web-lint

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test: test-all

# Run both Python and frontend tests
test-all: web-install
	@echo "Running Python tests..."
	pytest tests/ -v --tb=short
	@echo "Running frontend tests..."
	npm --prefix web test

# Python suite only — used by python-tests.yml, which provisions Python but
# not Node, unlike `test`/`test-all` above.
test-python:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-api:
	pytest tests/api/ -v --tb=short

# Both packages: `pyproject.toml`'s [tool.coverage.run] source lists team_maker
# and api, but --cov here overrides it, so api/ silently reported 0%.
test-cov:
	pytest tests/ --cov=team_maker --cov=api --cov-report=term-missing --cov-report=html

lint:
	ruff check team_maker/ api/ tests/

fmt:
	ruff format team_maker/ api/ tests/

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

# Run the example request to generate a sample team
example:
	python -m team_maker create --config examples/software_delivery_request.yaml --overwrite

# Show all available templates
list-templates:
	python -m team_maker list-templates

# API (Story 2.0) — the FastAPI seam AD-4 requires. Two-terminal dev flow:
# `make api-dev` here, `make web-dev` next door; the Next rewrite proxies
# /api/:path* to http://localhost:8000 so the browser stays same-origin.
#
# --reload already implies a single worker, so do NOT also pass --workers:
# uvicorn rejects the combination.
api-dev:
	uvicorn api.main:app --reload --port 8000

# Compose sessions live in an in-process dict (Story 2.0, AC 7). Raising the
# worker count above 1 gives each worker its own registry, and sessions then
# vanish at random for whichever requests land on the wrong process. The app
# logs a startup warning if WEB_CONCURRENCY disagrees with this.
api-serve:
	uvicorn api.main:app --port 8000 --workers 1

# Web app (Story 2.1) — standalone Next.js UI in web/
web-install:
	npm --prefix web ci

web-dev:
	npm --prefix web run dev

web-build:
	npm --prefix web run build

web-test:
	npm --prefix web test

web-lint:
	npm --prefix web run lint

# E2E tests with Playwright
test-e2e: web-install
	@echo "Installing Playwright browsers..."
	npm --prefix web run playwright:install
	@echo "Running E2E tests..."
	npm --prefix web run test:e2e
