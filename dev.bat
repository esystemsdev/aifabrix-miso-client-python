@echo off
REM Windows batch file for miso-client development
REM Usage: dev.bat [command]

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="install" goto install
if "%1"=="install-dev" goto install-dev
if "%1"=="test" goto test
if "%1"=="test-cov" goto test-cov
if "%1"=="lint" goto lint
if "%1"=="format" goto format
if "%1"=="type-check" goto type-check
if "%1"=="build" goto build
if "%1"=="check" goto check
if "%1"=="clean" goto clean
if "%1"=="all" goto all
goto unknown

:help
echo Miso Client Development Script
echo ==============================
echo.
echo Available commands:
echo   install      - Install the package
echo   install-dev  - Install with development dependencies
echo   test         - Run tests
echo   test-cov     - Run tests with coverage
echo   lint         - Run linting
echo   format       - Format code
echo   type-check   - Run type checking
echo   build        - Build the package
echo   check        - Check the built package
echo   clean        - Clean build artifacts
echo   all          - Run all checks and build
echo   help         - Show this help
echo.
echo Examples:
echo   dev.bat install-dev
echo   dev.bat test
echo   dev.bat all
goto end

:install
echo Installing package...
pip install -e .
goto end

:install-dev
echo Installing package with development dependencies...
pip install -e ".[dev]"
goto end

:test
echo Running tests...
python -m pytest tests/ -v
goto end

:test-cov
echo Running tests with coverage...
python -m pytest tests/ -v --cov=miso_client --cov-report=html --cov-report=xml
goto end

:lint
echo Running linting...
python -m ruff check miso_client/ tests/
goto end

:format
echo Formatting code...
python -m black miso_client/ tests/
python -m isort miso_client/ tests/
goto end

:type-check
echo Running type checking...
python -m mypy miso_client/ --ignore-missing-imports
goto end

:build
echo Building package...
python -m build
goto end

:check
echo Checking package...
python -m twine check dist/*
goto end

:clean
echo Cleaning build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.egg-info rmdir /s /q *.egg-info
if exist htmlcov rmdir /s /q htmlcov
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .mypy_cache rmdir /s /q .mypy_cache
if exist coverage.xml del coverage.xml
echo Cleaned build artifacts
goto end

:all
echo Running all checks and build...
call :clean
call :install-dev
call :lint
call :type-check
call :test-cov
call :build
call :check
echo All checks completed!
goto end

:unknown
echo Unknown command: %1
goto help

:end
