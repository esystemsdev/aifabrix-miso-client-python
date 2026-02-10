.PHONY: help install install-dev test test-cov test-integration lint format type-check build clean clean-venv publish test-publish venv all venv

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

PYTHON := python3
VENV := venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV_PYTHON) -m pip

# Check if venv exists, if not create it
venv: ## Create virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV); \
		echo "Virtual environment created at $(VENV)"; \
	else \
		echo "Virtual environment already exists at $(VENV)"; \
	fi

install: venv ## Install the package
	$(VENV_PIP) install -e .

install-dev: venv ## Install the package with development dependencies
	$(VENV_PIP) install -e ".[dev]"

test: venv ## Run tests (excludes integration tests)
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/

test-cov: venv ## Run tests with coverage (excludes integration tests)
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --cov=miso_client --cov-report=html --cov-report=xml

test-integration: venv ## Run integration tests against real controller (pytest, uses .env)
	$(VENV_PYTHON) -m pytest tests/integration/ -v --no-cov

test-integration-legacy: venv ## Run legacy integration test script
	$(VENV_PYTHON) test_integration.py

lint: venv ## Run linting
	$(VENV_PYTHON) -m ruff check miso_client/ tests/

format: venv ## Format code
	$(VENV_PYTHON) -m black miso_client/ tests/
	$(VENV_PYTHON) -m isort miso_client/ tests/

type-check: venv ## Run type checking
	$(VENV_PYTHON) -m mypy miso_client/ --ignore-missing-imports

build: venv ## Build the package
	$(VENV_PYTHON) -m build

check: venv ## Check the built package
	$(VENV_PYTHON) -m twine check dist/*

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -f coverage.xml

clean-venv: ## Remove virtual environment
	rm -rf $(VENV)

validate: venv ## Run lint + format + test (excludes integration tests)
	$(VENV_PYTHON) -m ruff check miso_client/ tests/
	$(VENV_PYTHON) -m black miso_client/ tests/
	$(VENV_PYTHON) -m isort miso_client/ tests/
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/

validate-api: venv ## Validate API endpoints via integration tests (uses .env)
	@echo "Running API endpoint integration tests..."
	@echo "Note: Tests require MISO_CLIENTID, MISO_CLIENTSECRET, and MISO_CONTROLLER_URL in .env"
	$(VENV_PYTHON) -m pytest tests/integration/ -v --no-cov

publish: venv ## Publish to PyPI
	$(VENV_PYTHON) -m twine upload dist/*

test-publish: venv ## Publish to Test PyPI
	$(VENV_PYTHON) -m twine upload --repository testpypi dist/*

all: venv format lint test test-integration ## Format, lint, and run all tests (unit + integration)

dev: venv install-dev ## Set up development environment
	@echo "Development environment set up. Run 'make test' to run tests."
	@echo "Virtual environment: $(VENV)"
	@echo "Activate with: source $(VENV)/bin/activate"
