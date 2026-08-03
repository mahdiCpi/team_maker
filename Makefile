.PHONY: install install-dev test test-unit test-integration lint fmt clean example web-install web-dev web-build web-test web-lint

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-cov:
	pytest tests/ --cov=team_maker --cov-report=term-missing --cov-report=html

lint:
	ruff check team_maker/ tests/

fmt:
	ruff format team_maker/ tests/

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

# Run the example request to generate a sample team
example:
	python -m team_maker create --config examples/software_delivery_request.yaml --overwrite

# Show all available templates
list-templates:
	python -m team_maker list-templates

# Web app (Story 2.1) — standalone Next.js UI in web/, no backend yet
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
