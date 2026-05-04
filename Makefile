.DEFAULT_GOAL := help

.PHONY: help install install-dev test test-cov test-integration test-integration-legacy test-manual lint format type-check build check clean clean-venv validate validate-api publish test-publish venv all dev format-silent lint-silent test-silent test-cov-silent test-integration-silent type-check-silent validate-silent

help: ## Show all commands
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

PYTHON := python3
VENV := venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV_PYTHON) -m pip

# Shared helper for silent targets (stores output in .temp/validation/)
define run_silent
mkdir -p .temp/validation; \
$(MAKE) --no-print-directory $(1) > .temp/validation/$(2) 2>&1 || { echo "[FAILED] $(1)-silent -> .temp/validation/$(2)"; exit 1; }; \
echo "[OK] $(1)-silent -> .temp/validation/$(2)"
endef

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
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual/

test-silent: ## Run tests in silent mode (writes .temp/validation/04-test)
	@$(call run_silent,test,04-test)

test-cov: venv ## Run tests with coverage (excludes integration tests)
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual/ --cov=miso_client --cov-report=html --cov-report=xml

test-cov-silent: ## Run coverage tests in silent mode (writes .temp/validation/05-test-cov)
	@$(call run_silent,test-cov,05-test-cov)

test-integration: venv ## Run integration tests (requires: aifabrix auth status --validate succeeds; no skips, failures shown as errors)
	$(VENV_PYTHON) -m pytest tests/integration/ -v --no-cov

test-integration-silent: ## Run integration tests in silent mode (writes .temp/validation/06-test-integration)
	@$(call run_silent,test-integration,06-test-integration)

test-integration-legacy: venv ## Run legacy integration test script

	$(VENV_PYTHON) test_integration.py
test-manual: venv ## Run manual-only tests (not run by make test)
	$(VENV_PYTHON) -m pytest tests/manual/ -v

lint: venv ## Run linting
	$(VENV_PYTHON) -m ruff check miso_client/ tests/

lint-silent: ## Run lint in silent mode (writes .temp/validation/02-lint)
	@$(call run_silent,lint,02-lint)

format: venv ## Format code
	$(VENV_PYTHON) -m black miso_client/ tests/
	$(VENV_PYTHON) -m isort miso_client/ tests/

format-silent: ## Run format in silent mode (writes .temp/validation/01-format)
	@$(call run_silent,format,01-format)

type-check: venv ## Run type checking
	$(VENV_PYTHON) -m mypy miso_client/ --ignore-missing-imports

type-check-silent: ## Run type-check in silent mode (writes .temp/validation/03-type-check)
	@$(call run_silent,type-check,03-type-check)

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
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual/

validate-silent: ## Run validate chain in silent mode (logs in .temp/validation/)
	@$(MAKE) --no-print-directory format-silent
	@$(MAKE) --no-print-directory lint-silent
	@$(MAKE) --no-print-directory type-check-silent
	@$(MAKE) --no-print-directory test-silent
	@echo "[OK] validate-silent logs: .temp/validation/{01-format,02-lint,03-type-check,04-test}"

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
