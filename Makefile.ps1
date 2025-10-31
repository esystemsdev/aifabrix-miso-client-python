# PowerShell Makefile for miso-client development
# Usage: .\Makefile.ps1 <target>

param(
    [Parameter(Position=0)]
    [string]$Target = "help"
)

function Show-Help {
    Write-Host "Available commands:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  install      - Install the package"
    Write-Host "  install-dev  - Install the package with development dependencies"
    Write-Host "  test         - Run tests"
    Write-Host "  test-cov     - Run tests with coverage"
    Write-Host "  lint         - Run linting"
    Write-Host "  format       - Format code"
    Write-Host "  type-check   - Run type checking"
    Write-Host "  build        - Build the package"
    Write-Host "  check        - Check the built package"
    Write-Host "  clean        - Clean build artifacts"
    Write-Host "  validate     - Run lint + format + test"
    Write-Host "  all          - Run all checks and build"
    Write-Host "  help         - Show this help"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\Makefile.ps1 install-dev"
    Write-Host "  .\Makefile.ps1 test"
    Write-Host "  .\Makefile.ps1 all"
}

function Install-Package {
    Write-Host "Installing package..." -ForegroundColor Yellow
    pip install -e .
}

function Install-DevPackage {
    Write-Host "Installing package with development dependencies..." -ForegroundColor Yellow
    pip install -e ".[dev]"
}

function Run-Tests {
    Write-Host "Running tests..." -ForegroundColor Yellow
    python -m pytest tests/ -v
}

function Run-TestsWithCoverage {
    Write-Host "Running tests with coverage..." -ForegroundColor Yellow
    python -m pytest tests/ -v --cov=miso_client --cov-report=html --cov-report=xml
}

function Run-Linting {
    Write-Host "Running linting..." -ForegroundColor Yellow
    python -m ruff check miso_client/ tests/
}

function Format-Code {
    Write-Host "Formatting code..." -ForegroundColor Yellow
    python -m black miso_client/ tests/
    python -m isort miso_client/ tests/
}

function Run-TypeCheck {
    Write-Host "Running type checking..." -ForegroundColor Yellow
    python -m mypy miso_client/ --ignore-missing-imports
}

function Build-Package {
    Write-Host "Building package..." -ForegroundColor Yellow
    python -m build
}

function Check-Package {
    Write-Host "Checking package..." -ForegroundColor Yellow
    python -m twine check dist/*
}

function Clean-Artifacts {
    Write-Host "Cleaning build artifacts..." -ForegroundColor Yellow
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    Get-ChildItem -Path . -Filter "*.egg-info" -Directory | Remove-Item -Recurse -Force
    if (Test-Path "htmlcov") { Remove-Item -Recurse -Force "htmlcov" }
    if (Test-Path ".pytest_cache") { Remove-Item -Recurse -Force ".pytest_cache" }
    if (Test-Path ".mypy_cache") { Remove-Item -Recurse -Force ".mypy_cache" }
    if (Test-Path "coverage.xml") { Remove-Item -Force "coverage.xml" }
    Write-Host "Cleaned build artifacts" -ForegroundColor Green
}

function Run-Validate {
    Write-Host "Running validation (lint + format + test)..." -ForegroundColor Yellow
    Run-Linting
    Format-Code
    Run-Tests
    Write-Host "Validation completed!" -ForegroundColor Green
}

function Run-All {
    Write-Host "Running all checks and build..." -ForegroundColor Yellow
    Clean-Artifacts
    Install-DevPackage
    Run-Linting
    Run-TypeCheck
    Run-TestsWithCoverage
    Build-Package
    Check-Package
    Write-Host "All checks completed!" -ForegroundColor Green
}

# Main script logic
switch ($Target.ToLower()) {
    "install" { Install-Package }
    "install-dev" { Install-DevPackage }
    "test" { Run-Tests }
    "test-cov" { Run-TestsWithCoverage }
    "lint" { Run-Linting }
    "format" { Format-Code }
    "type-check" { Run-TypeCheck }
    "build" { Build-Package }
    "check" { Check-Package }
    "clean" { Clean-Artifacts }
    "validate" { Run-Validate }
    "all" { Run-All }
    "help" { Show-Help }
    default { 
        Write-Host "Unknown target: $Target" -ForegroundColor Red
        Show-Help
        exit 1
    }
}

