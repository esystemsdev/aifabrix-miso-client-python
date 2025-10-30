.PHONY: help install install-dev test test-cov lint format type-check build clean publish test-publish

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

install-dev: ## Install the package with development dependencies
	pip install -e ".[dev]"

test: ## Run tests
	python -m pytest tests/ -v

test-cov: ## Run tests with coverage
	python -m pytest tests/ -v --cov=miso_client --cov-report=html --cov-report=xml

lint: ## Run linting
	python -m ruff check miso_client/ tests/

format: ## Format code
	python -m black miso_client/ tests/
	python -m isort miso_client/ tests/

type-check: ## Run type checking
	python -m mypy miso_client/ --ignore-missing-imports

build: ## Build the package
	python -m build

check: ## Check the built package
	python -m twine check dist/*

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -f coverage.xml

publish: ## Publish to PyPI
	python -m twine upload dist/*

test-publish: ## Publish to Test PyPI
	python -m twine upload --repository testpypi dist/*

all: clean install-dev lint type-check test-cov build check ## Run all checks and build

dev: install-dev ## Set up development environment
	@echo "Development environment set up. Run 'make test' to run tests."
