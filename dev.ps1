# PowerShell development script for miso-client
# Usage: .\dev.ps1 [command]

param(
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "Miso Client Development Script" -ForegroundColor Green
    Write-Host "==============================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Available commands:"
    Write-Host "  install      - Install the package"
    Write-Host "  install-dev  - Install with development dependencies"
    Write-Host "  test         - Run tests"
    Write-Host "  test-cov     - Run tests with coverage"
    Write-Host "  lint         - Run linting"
    Write-Host "  format       - Format code"
    Write-Host "  type-check   - Run type checking"
    Write-Host "  build        - Build the package"
    Write-Host "  check        - Check the built package"
    Write-Host "  clean        - Clean build artifacts"
    Write-Host "  all          - Run all checks and build"
    Write-Host "  help         - Show this help"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\dev.ps1 install-dev"
    Write-Host "  .\dev.ps1 test"
    Write-Host "  .\dev.ps1 all"
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
    if (Test-Path "*.egg-info") { Remove-Item -Recurse -Force "*.egg-info" }
    if (Test-Path "htmlcov") { Remove-Item -Recurse -Force "htmlcov" }
    if (Test-Path ".pytest_cache") { Remove-Item -Recurse -Force ".pytest_cache" }
    if (Test-Path ".mypy_cache") { Remove-Item -Recurse -Force ".mypy_cache" }
    if (Test-Path "coverage.xml") { Remove-Item -Force "coverage.xml" }
    Write-Host "Cleaned build artifacts" -ForegroundColor Green
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
switch ($Command.ToLower()) {
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
    "all" { Run-All }
    "help" { Show-Help }
    default { 
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Show-Help
    }
}
