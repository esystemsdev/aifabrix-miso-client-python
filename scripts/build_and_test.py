#!/usr/bin/env python3
"""
Build and test script for miso-client package.

This script helps with local development by running tests, building the package,
and performing basic validation.
"""

import os
import sys
import subprocess
import shutil

def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}...")
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e.stderr}")
        return False

def clean_build():
    """Clean build artifacts."""
    print("\n🧹 Cleaning build artifacts...")
    
    dirs_to_clean = ['build', 'dist', 'miso_client.egg-info', 'htmlcov', '.pytest_cache', '.mypy_cache']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed {dir_name}/")
    
    files_to_clean = ['coverage.xml']
    for file_name in files_to_clean:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"Removed {file_name}")

def run_tests():
    """Run the test suite."""
    return run_command([
        sys.executable, '-m', 'pytest', 'tests/', '-v', '--cov=miso_client', 
        '--cov-report=html', '--cov-report=xml'
    ], "Running tests")

def run_linting():
    """Run code quality checks."""
    success = True
    
    # Run ruff
    success &= run_command([sys.executable, '-m', 'ruff', 'check', 'miso_client/', 'tests/'], "Linting with ruff")
    
    # Run mypy
    success &= run_command([sys.executable, '-m', 'mypy', 'miso_client/', '--ignore-missing-imports'], "Type checking with mypy")
    
    return success

def build_package():
    """Build the package."""
    return run_command([
        sys.executable, '-m', 'build'
    ], "Building package")

def check_package():
    """Check the built package."""
    return run_command([
        sys.executable, '-m', 'twine', 'check', 'dist/*'
    ], "Checking package")

def install_dependencies():
    """Install required dependencies."""
    return run_command([
        sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-r', 'requirements-test.txt'
    ], "Installing dependencies")

def main():
    """Main function."""
    print("🚀 Miso Client Build and Test Script")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('pyproject.toml'):
        print("❌ Error: pyproject.toml not found. Please run this script from the project root.")
        sys.exit(1)
    
    # Parse command line arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ['all']
    
    success = True
    
    if 'clean' in args or 'all' in args:
        clean_build()
    
    if 'deps' in args or 'all' in args:
        success &= install_dependencies()
    
    if 'lint' in args or 'all' in args:
        success &= run_linting()
    
    if 'test' in args or 'all' in args:
        success &= run_tests()
    
    if 'build' in args or 'all' in args:
        success &= build_package()
        if success:
            success &= check_package()
    
    if success:
        print("\n🎉 All operations completed successfully!")
        print("\nNext steps:")
        print("1. Review the test results and coverage report")
        print("2. Check the built package in dist/")
        print("3. If everything looks good, you can publish to PyPI")
    else:
        print("\n❌ Some operations failed. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
