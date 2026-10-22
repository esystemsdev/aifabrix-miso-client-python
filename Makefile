.DEFAULT_GOAL := help

.PHONY: test-encryption-e2e test-token-lifecycle-e2e help install install-dev install-build-tools install-node-tools test test-cov test-integration test-integration-legacy test-manual lint format basedpyright type-check build check clean clean-venv validate validate-api publish test-publish venv all dev format-silent lint-silent basedpyright-silent test-silent test-cov-silent test-integration-silent type-check-silent validate-silent lock check-dev-tools check-platform-tools platform-baseline-check platform-baseline-check-silent

help: ## Show all commands
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

PYTHON ?= python3
VENV ?= venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV_PYTHON) -m pip
BASEDPYRIGHT_PATHS ?= miso_client tests
RUNTIME_LOCK := requirements/runtime.lock
DEV_LOCK := requirements/dev.lock
BUILD_LOCK := requirements/build.lock
NODE ?= node
PNPM ?= pnpm

define install_hashed_environment
	@set -eu; \
	locks="$(1)"; \
	marker="$(VENV)/.aifabrix-$(2)-environment.sha256"; \
	digest="$$(for lock in $$locks; do sha256sum "$$lock"; done | sha256sum | awk '{print $$1}')"; \
	current="$$(test -f "$$marker" && cat "$$marker" || true)"; \
	if [ "$$current" != "$$digest" ]; then \
		echo "Installing coherent hashed $(2) environment from $$locks..."; \
		rm -f -- "$(VENV)"/.aifabrix-*-environment.sha256; \
		set --; for lock in $$locks; do set -- "$$@" -r "$$lock"; done; \
		$(VENV_PIP) install --disable-pip-version-check --require-hashes "$$@"; \
		printf '%s\n' "$$digest" > "$$marker.tmp"; \
		mv -- "$$marker.tmp" "$$marker"; \
	else \
		echo "Coherent hashed $(2) environment is current."; \
	fi
endef

# Shared helper for silent targets (stores output in .temp/validation/)
define run_silent
mkdir -p .temp/validation; \
$(MAKE) --no-print-directory $(1) > .temp/validation/$(2) 2>&1 || { echo "[FAILED] $(1)-silent -> .temp/validation/$(2)"; exit 1; }; \
echo "[OK] $(1)-silent -> .temp/validation/$(2)"
endef

# Create or safely refresh the managed venv when its interpreter changes.
venv: ## Create an interpreter-aware virtual environment
	@set -eu; \
	root="$$(pwd -P)"; \
	requested="$(VENV)"; \
	if [ -L "$$requested" ]; then echo "Refusing symlink VENV: $$requested"; exit 2; fi; \
	target="$$($(PYTHON) -c 'from pathlib import Path; print(Path("$(VENV)").resolve())')"; \
	case "$$target" in "$$root"/*) ;; *) echo "Refusing VENV outside repository: $$target"; exit 2 ;; esac; \
	selected="$$($(PYTHON) -c 'import os, sys; print(f"{os.path.realpath(sys._base_executable)}|{sys.version_info.major}.{sys.version_info.minor}")')"; \
	if [ -d "$$target" ]; then \
		if [ -n "$$(find "$$target" -mindepth 1 -maxdepth 1 -print -quit)" ]; then \
			managed=false; \
			if [ -f "$$target/.aifabrix-managed-venv" ] && [ "$$(cat "$$target/.aifabrix-managed-venv")" = "miso-client-python" ] && [ -f "$$target/pyvenv.cfg" ] && [ -x "$$target/bin/python" ]; then managed=true; fi; \
			if [ "$$target" = "$$root/venv" ] && [ -f "$$target/pyvenv.cfg" ] && [ -x "$$target/bin/python" ]; then managed=true; fi; \
			if [ "$$managed" != true ]; then echo "Refusing nonempty unmanaged VENV: $$target"; exit 2; fi; \
			current="$$("$$target/bin/python" -c 'import os, sys; print(f"{os.path.realpath(sys._base_executable)}|{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"; \
			if [ "$$current" != "$$selected" ]; then \
				echo "Refreshing managed virtual environment: expected $$selected, found $${current:-invalid}"; \
				rm -rf -- "$$target"; \
			fi; \
		fi; \
	fi; \
	if [ ! -x "$$target/bin/python" ]; then \
		echo "Creating virtual environment with $(PYTHON)..."; \
		$(PYTHON) -m venv "$$target"; \
	fi; \
	printf '%s\n' 'miso-client-python' > "$$target/.aifabrix-managed-venv.tmp"; \
	mv -- "$$target/.aifabrix-managed-venv.tmp" "$$target/.aifabrix-managed-venv"; \
	printf '%s\n' "$$selected" > "$$target/.aifabrix-python-identity.tmp"; \
	mv -- "$$target/.aifabrix-python-identity.tmp" "$$target/.aifabrix-python-identity"; \
	echo "Virtual environment ready at $(VENV) ($$selected)"

install-build-tools: venv ## Install the controlled build/bootstrap environment
	$(call install_hashed_environment,$(BUILD_LOCK),build)

install: venv ## Install locked runtime/build dependencies and editable package
	$(call install_hashed_environment,$(BUILD_LOCK) $(RUNTIME_LOCK),runtime)
	$(VENV_PIP) install --disable-pip-version-check --no-deps --no-build-isolation -e .

install-dev: venv ## Install one coherent locked development/build environment
	$(call install_hashed_environment,$(BUILD_LOCK) $(DEV_LOCK),dev)
	$(VENV_PIP) install --disable-pip-version-check --no-deps --no-build-isolation -e .

install-node-tools: ## Install frozen development-only platform checker tools
	@$(NODE) -e 'if (process.version !== "v24.22.1") { throw new Error(`Node 24.22.1 is required, found $${process.version}`); }'
	@test "$$($(PNPM) --version)" = "12.11.2" || { echo "pnpm 12.11.2 is required. Activate the packageManager version first."; exit 2; }
	$(PNPM) install --frozen-lockfile --ignore-scripts

check-dev-tools: venv ## Fail usefully when development tools are not provisioned
	@expected="$$(for lock in "$(BUILD_LOCK)" "$(DEV_LOCK)"; do sha256sum "$$lock"; done | sha256sum | awk '{print $$1}')"; current="$$(test -f "$(VENV)/.aifabrix-dev-environment.sha256" && cat "$(VENV)/.aifabrix-dev-environment.sha256" || true)"; test "$$current" = "$$expected" || { echo "Development locks are not installed or are stale. Run make install-dev."; exit 2; }
	@$(VENV_PYTHON) -c 'import importlib.util as i, sys; modules=("black", "isort", "mypy", "basedpyright", "pytest", "ruff"); missing=[m for m in modules if i.find_spec(m) is None]; sys.exit("Missing development tools: " + ", ".join(missing) + ". Run make install-dev.") if missing else None'

check-platform-tools: ## Fail usefully when platform checker tools are not provisioned
	@command -v $(NODE) >/dev/null 2>&1 || { echo "Node 24.22.1 is required. Run make install-node-tools after selecting .nvmrc."; exit 2; }
	@$(NODE) -e 'if (process.version !== "v24.22.1") { throw new Error(`Node 24.22.1 is required, found $${process.version}`); }'
	@$(NODE) -e 'Promise.all([import("js-yaml"), import("smol-toml")]).catch(() => { console.error("Platform checker dependencies are missing. Run make install-node-tools."); process.exit(2); })'

platform-baseline-check: check-platform-tools ## Run the accepted canonical platform baseline checker
	$(NODE) scripts/platform-baseline-check.mjs --profile python-sdk

platform-baseline-check-silent: ## Run platform baseline check silently (writes .temp/validation/05-platform-baseline)
	@$(call run_silent,platform-baseline-check,05-platform-baseline)

lock: install-build-tools ## Regenerate hashed runtime/development/build locks
	CUSTOM_COMPILE_COMMAND='make lock' $(VENV_PYTHON) -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --output-file=$(RUNTIME_LOCK) requirements/runtime.in
	CUSTOM_COMPILE_COMMAND='make lock' $(VENV_PYTHON) -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --output-file=$(DEV_LOCK) requirements/dev.in
	CUSTOM_COMPILE_COMMAND='make lock' $(VENV_PYTHON) -m piptools compile --generate-hashes --allow-unsafe --resolver=backtracking --output-file=$(BUILD_LOCK) requirements/build.in

test: check-dev-tools ## Run tests (excludes integration tests)
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual/

test-silent: ## Run tests in silent mode (writes .temp/validation/04-test)
	@$(call run_silent,test,04-test)

test-cov: check-dev-tools ## Run tests with coverage (excludes integration tests)
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual/ --cov=miso_client --cov-report=html --cov-report=xml

test-cov-silent: ## Run coverage tests in silent mode (writes .temp/validation/05-test-cov)
	@$(call run_silent,test-cov,05-test-cov)

test-integration: check-dev-tools ## Run integration tests (requires: aifabrix auth status --validate succeeds; no skips, failures shown as errors)
	$(VENV_PYTHON) -m pytest tests/integration/ -v --no-cov

test-token-lifecycle-e2e: check-dev-tools ## Run real controller token lifecycle tests (requires registered test app and valid CLI auth)
	@mkdir -p .temp/validation
	$(VENV_PYTHON) -m pytest tests/integration/test_client_token_lifecycle.py -o addopts= -o junit_family=legacy --no-cov --tb=short -v --junitxml=.temp/validation/52-live-e2e.xml

test-integration-silent: ## Run integration tests in silent mode (writes .temp/validation/06-test-integration)
	@$(call run_silent,test-integration,06-test-integration)

test-integration-legacy: check-dev-tools ## Run legacy integration test script

	$(VENV_PYTHON) test_integration.py
test-manual: check-dev-tools ## Run manual-only tests (not run by make test)
	$(VENV_PYTHON) -m pytest tests/manual/ -v

lint: check-dev-tools ## Run linting
	$(VENV_PYTHON) -m ruff check miso_client/ tests/

lint-silent: ## Run lint in silent mode (writes .temp/validation/02-lint)
	@$(call run_silent,lint,02-lint)

format: check-dev-tools ## Format code
	$(VENV_PYTHON) -m black miso_client/ tests/
	$(VENV_PYTHON) -m isort miso_client/ tests/

format-silent: ## Run format in silent mode (writes .temp/validation/01-format)
	@$(call run_silent,format,01-format)

type-check: check-dev-tools ## Run type checking
	$(VENV_PYTHON) -m mypy miso_client/ --ignore-missing-imports

type-check-silent: ## Run type-check in silent mode (writes .temp/validation/03-type-check)
	@$(call run_silent,type-check,03-type-check)

basedpyright: check-dev-tools ## Run basedpyright (set BASEDPYRIGHT_PATHS for targeted checks)
	$(VENV_PYTHON) -m basedpyright $(BASEDPYRIGHT_PATHS)

basedpyright-silent: ## Run basedpyright in silent mode (writes .temp/validation/03a-basedpyright)
	@$(call run_silent,basedpyright,03a-basedpyright)

build: install-build-tools ## Build the package with controlled PEP 517 inputs
	$(VENV_PYTHON) -m build --no-isolation

check: install-build-tools ## Check the built package
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
	@set -eu; \
	root="$$(pwd -P)"; \
	requested="$(VENV)"; \
	if [ -L "$$requested" ]; then echo "Refusing symlink VENV: $$requested"; exit 2; fi; \
	target="$$($(PYTHON) -c 'from pathlib import Path; print(Path("$(VENV)").resolve())')"; \
	case "$$target" in "$$root"/*) ;; *) echo "Refusing VENV outside repository: $$target"; exit 2 ;; esac; \
	if [ ! -e "$$target" ]; then exit 0; fi; \
	managed=false; \
	if [ -f "$$target/.aifabrix-managed-venv" ] && [ "$$(cat "$$target/.aifabrix-managed-venv")" = "miso-client-python" ] && [ -f "$$target/pyvenv.cfg" ] && [ -x "$$target/bin/python" ]; then managed=true; fi; \
	if [ "$$target" = "$$root/venv" ] && [ -f "$$target/pyvenv.cfg" ] && [ -x "$$target/bin/python" ]; then managed=true; fi; \
	if [ "$$managed" != true ]; then echo "Refusing to remove unmanaged VENV: $$target"; exit 2; fi; \
	rm -rf -- "$$target"

validate: check-dev-tools ## Run the required local validation chain
	$(VENV_PYTHON) -m black miso_client/ tests/
	$(VENV_PYTHON) -m isort miso_client/ tests/
	$(VENV_PYTHON) -m ruff check miso_client/ tests/
	$(VENV_PYTHON) -m basedpyright $(BASEDPYRIGHT_PATHS)
	$(VENV_PYTHON) -m mypy miso_client/ --ignore-missing-imports
	$(VENV_PYTHON) -m pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual/
	$(MAKE) --no-print-directory platform-baseline-check

validate-silent: ## Run validate chain in silent mode (logs in .temp/validation/)
	@$(MAKE) --no-print-directory format-silent
	@$(MAKE) --no-print-directory lint-silent
	@$(MAKE) --no-print-directory basedpyright-silent
	@$(MAKE) --no-print-directory type-check-silent
	@$(MAKE) --no-print-directory test-silent
	@$(MAKE) --no-print-directory platform-baseline-check-silent
	@echo "[OK] validate-silent logs: .temp/validation/{01-format,02-lint,03a-basedpyright,03-type-check,04-test,05-platform-baseline}"

validate-api: check-dev-tools ## Validate API endpoints via integration tests (uses .env)
	@echo "Running API endpoint integration tests..."
	@echo "Note: Tests require MISO_CLIENTID, MISO_CLIENTSECRET, and MISO_CONTROLLER_URL in .env"
	$(VENV_PYTHON) -m pytest tests/integration/ -v --no-cov

publish: install-build-tools ## Publish to PyPI
	$(VENV_PYTHON) -m twine upload dist/*

test-publish: install-build-tools ## Publish to Test PyPI
	$(VENV_PYTHON) -m twine upload --repository testpypi dist/*

all: venv format lint test test-integration ## Format, lint, and run all tests (unit + integration)

dev: venv install-dev ## Set up development environment
	@echo "Development environment set up. Run 'make test' to run tests."
	@echo "Virtual environment: $(VENV)"
	@echo "Activate with: source $(VENV)/bin/activate"


test-encryption-e2e: check-dev-tools ## Round-trip a throwaway value through real encrypt/decrypt endpoints
	@mkdir -p .temp/validation
	$(VENV_PYTHON) -m pytest tests/manual/test_encryption_roundtrip_live.py -o addopts= -o junit_family=legacy --no-cov --tb=short -v --junitxml=.temp/validation/52-encryption-live.xml
