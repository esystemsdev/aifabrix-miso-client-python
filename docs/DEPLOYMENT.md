# Deployment Guide

This guide explains how to deploy the `miso-client` Python package to PyPI and set up automated workflows.

## Prerequisites

1. **GitHub Repository**: The code should be in a GitHub repository
2. **PyPI Account**: Create an account at [pypi.org](https://pypi.org)
3. **GitHub Secrets**: Configure required secrets in your GitHub repository

## Setup Steps

### 1. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions, and add:

- `PYPI_TOKEN`: Your PyPI API token (create at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/))

### 2. Version Management

Use `/repair-release` to prepare the version and changelog locally. Keep
`pyproject.toml`, `setup.py`, `miso_client/__init__.py`, and `.bumpversion.cfg`
in sync. Preparation does not commit, tag or publish. If using `bump2version`
manually, pass `--no-commit --no-tag` because the configuration enables both.

## Automated Workflows

### Test Workflow (`.github/workflows/test.yml`)

Runs on pushes and pull requests targeting `main`, `dev`, and
`release/miso-client-python-*`. Required jobs run the ordered formatting, lint,
basedpyright, mypy and bounded pytest chain on Python 3.11–3.14 using the committed
hash-checked dependency set. Python 3.15 readiness is visible but non-blocking.

### Manual CodeQL (`.github/workflows/codeql-manual.yml`)

Dispatched on the release branch before PR handoff and on the approved tag before
publication. Scans Python and GitHub Actions. Review both SARIF artifacts and
require zero findings; a green workflow alone does not prove zero findings.

### Publish Workflow (`.github/workflows/publish.yml`)

A published GitHub Release triggers package validation, build, package checks and
PyPI upload on Python 3.14 using the repository `PYPI_TOKEN` secret. Manual dispatch
is available for retries pinned to the approved tag, with the matching metadata version.
Branch pushes and tag pushes alone do not publish. There is no automatic version
bump or standalone build/release workflow. The workflow does not currently bind
to a GitHub environment; an environment-only secret is insufficient.

## Manual Deployment

Use these commands for local package checks and Test PyPI. Production publication
follows the reviewed release process below.

### 1. Build the Package

```bash
# Install the committed build toolchain
make PYTHON=python3 VENV=venv install-build-tools

# Build with controlled PEP 517 inputs
make PYTHON=python3 VENV=venv build

# Check the package
make PYTHON=python3 VENV=venv check
```

### 2. Upload to Test PyPI

```bash
# Upload to Test PyPI first (recommended)
twine upload --repository testpypi dist/*

```

### 3. Install from PyPI

```bash
# Install the latest version
pip install miso-client

# Install a specific version
pip install miso-client==0.1.0

# Install with development dependencies
pip install "miso-client[dev]"
```

## Using in Other Applications

### 1. Add to requirements.txt

```txt
miso-client>=0.1.0
```

### 2. Install in your project

```bash
pip install -r requirements.txt
```

### 3. Use in your code

```python
from miso_client import MisoClient, load_config

# Load configuration from environment
config = load_config()

# Create client
client = MisoClient(config)
await client.initialize()

# Use the client
is_valid = await client.validate_token(token)
```

## Development Setup

Use `make` for development commands (works on Linux, macOS, and Windows with Git Bash/WSL):

```bash
# Python 3.14 is selected by .python-version when the version manager supports it.
# PYTHON can explicitly select any supported Python 3.11–3.14 interpreter.
make PYTHON=python3 VENV=venv install-dev
make NODE=node PNPM=pnpm install-node-tools

# Run the required ordered validation chain
make PYTHON=python3 VENV=venv validate-silent

# Regenerate all hash-checked locks with the pinned build toolchain
make PYTHON=python3 VENV=venv lock

# Individual commands
make test
make lint
make format
make build
```

The Make targets install third-party development and build dependencies from
`requirements/*.lock` with hash verification, then install the local SDK without
re-resolving dependencies. A managed virtual environment is refreshed when its
selected interpreter changes; nonempty unmanaged directories and symlink targets
are refused. Node 24 and pnpm are used only by repository baseline tooling and are
not Python package runtime dependencies. `make platform-baseline-check` and
`pnpm platform-baseline-check` run the same byte-identical canonical checker;
normal validation includes that check after the ordered Python gates.

### 1. Clone and Install

```bash
git clone https://github.com/your-org/miso-client-python.git
cd miso-client-python

# Install the locked development environment and editable SDK
make PYTHON=python3 VENV=venv install-dev

# Install frozen development-only checker tools
make NODE=node PNPM=pnpm install-node-tools
```

### 2. Run Tests

```bash
make test
make test-cov

# Or directly with pytest
pytest tests/ -v
pytest tests/ -v --cov=miso_client --cov-report=html
```

### 3. Code Quality

```bash
make format
make lint
make type-check
make validate  # Runs format, lint, basedpyright, mypy, then tests
```

## Release Process

Development → release branch → reviewed PR to `main` → GitHub Release → PyPI.

1. On `dev` (or the current development branch), run
   [/push-release-branch](../.cursor/commands/push-release-branch.md).
   It prepares or reuses an unpublished version, runs local validation, and
   pushes to `release/miso-client-python-X.Y.0`. For example, `4.20.3` uses
   `release/miso-client-python-4.20.0`; patch releases share that branch.
2. Require tests and zero CodeQL findings for the exact release commit. Open or
   reuse the release branch's PR to `main`, and provide its review link.
3. A human reviews and merges the PR after required checks pass. Configure main
   branch protection to require PR review and the Test check. Command instructions
   do not themselves enforce GitHub repository settings.
4. Run [/push-github](../.cursor/commands/push-github.md) after merge. It verifies
   the merged PR and main commit, creates an immutable annotated `vX.Y.Z` tag on
   that commit, checks CodeQL on the tag, and publishes the GitHub Release.
5. Require the matching publish workflow to succeed and verify the version on
   PyPI before reporting completion.

Never push directly to `main` as part of this process. Keep release fixes in the
same line by merging them back into development before the next promotion.
Existing patch-named release branches are inspected for missing fixes before
creating the `X.Y.0` branch; they are not automatically renamed or deleted.

`/push-release-branch silent` combines commit/push approval after preparation;
PR creation remains separate unless explicitly authorized. It does not publish.
An interrupted run reuses prepared metadata, existing PRs and matching tags.
Never move a release tag or overwrite published package contents. Fixes requiring
changed release contents go through a new version and the same review process.

## Troubleshooting

### Common Issues

1. **Build fails**: Check that all dependencies are properly specified in `pyproject.toml`
2. **Upload fails**: Verify `PYPI_TOKEN` is correct and has upload permissions
3. **Tests fail**: Ensure all test dependencies are installed and environment variables are set
4. **Import errors**: Check that the package is properly installed with `pip install -e .`

### Getting Help

- Check the [GitHub Issues](https://github.com/your-org/miso-client-python/issues)
- Review the [API Documentation](docs/api-reference.md)
- See [Troubleshooting Guide](docs/troubleshooting.md)

## Security Considerations

1. **API Tokens**: Never commit API tokens to the repository
2. **Environment Variables**: Use GitHub Secrets for sensitive configuration
3. **Dependencies**: Regularly update dependencies to patch security vulnerabilities
4. **Code Review**: Require code review for all changes to the main branch

## Monitoring

- **PyPI Downloads**: Monitor package downloads on PyPI
- **GitHub Actions**: Check workflow status in the Actions tab
- **Code Coverage**: Monitor coverage trends in Codecov
- **Dependencies**: Use Dependabot for automated dependency updates
