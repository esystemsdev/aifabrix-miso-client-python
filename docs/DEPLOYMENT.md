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

### 2. Configure GitHub Environments

1. Go to Settings → Environments
2. Create a new environment called `pypi`
3. Add the `PYPI_TOKEN` secret to this environment
4. Optionally, add protection rules (required reviewers, etc.)

### 3. Version Management

The project uses `bump2version` for automated version management:

```bash
# Install bump2version
pip install bump2version

# Bump patch version (0.1.0 → 0.1.1)
bump2version patch

# Bump minor version (0.1.0 → 0.2.0)
bump2version minor

# Bump major version (0.1.0 → 1.0.0)
bump2version major
```

## Automated Workflows

### Test Workflow (`.github/workflows/test.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**What it does:**
- Tests on Python 3.8, 3.9, 3.10, 3.11, 3.12
- Runs linting with `ruff`
- Runs type checking with `mypy`
- Runs tests with `pytest` and coverage
- Uploads coverage to Codecov

### Build Workflow (`.github/workflows/build.yml`)

**Triggers:**
- Push to `main` branch
- Pull requests to `main` branch

**What it does:**
- Builds the package using `python -m build`
- Checks the package with `twine check`
- Uploads build artifacts for download

### Publish Workflow (`.github/workflows/publish.yml`)

**Triggers:**
- When a release is published
- Manual workflow dispatch

**What it does:**
- Builds the package
- Publishes to PyPI using the `PYPI_TOKEN`

### Release Workflow (`.github/workflows/release.yml`)

**Triggers:**
- Push to `main` branch
- Manual workflow dispatch

**What it does:**
- Automatically bumps version
- Creates a git tag
- Pushes changes and tags
- Creates a GitHub release

## Manual Deployment

### 1. Build the Package

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the package
twine check dist/*
```

### 2. Upload to PyPI

```bash
# Upload to Test PyPI first (recommended)
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
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
# Install with development dependencies
make install-dev

# Run all checks and build
make all

# Run validation (lint + format + test)
make validate

# Individual commands
make test
make lint
make format
make build
```

### 1. Clone and Install

```bash
git clone https://github.com/your-org/miso-client-python.git
cd miso-client-python

# Install in development mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
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
make validate  # Runs lint + format + test
```

## Release Process

### Automated Release (Recommended)

1. Push changes to `main` branch
2. The release workflow will automatically:
   - Bump the version
   - Create a git tag
   - Push changes
   - Create a GitHub release
3. The publish workflow will automatically publish to PyPI

### Manual Release

1. Update version in `pyproject.toml` and `miso_client/__init__.py`
2. Update `CHANGELOG.md`
3. Create a git tag: `git tag v0.1.0`
4. Push changes and tags: `git push && git push --tags`
5. Create a GitHub release
6. The publish workflow will automatically publish to PyPI

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
