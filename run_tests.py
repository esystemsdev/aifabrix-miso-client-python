#!/usr/bin/env python3
"""
Test runner for MisoClient SDK.

This script runs the unit tests for the MisoClient SDK package.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run MisoClient SDK tests."""
    # Change to the miso_client directory
    miso_client_dir = Path(__file__).parent
    os.chdir(miso_client_dir)
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--cov=miso_client",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-report=xml:coverage.xml",
    ]
    
    print(f"Running tests in: {miso_client_dir}")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
