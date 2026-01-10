"""
Integration test for API endpoints validation.

This test validates that all API endpoints can be called successfully.
It tests against a real controller using credentials from .env file.

The test gracefully skips if the controller is not available (don't fail CI/CD).
"""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load environment variables from project root .env file
env_path = project_root / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass  # dotenv not installed, continue without it


@pytest.mark.skipif(
    not os.getenv("MISO_CLIENTID")
    or not os.getenv("MISO_CLIENTSECRET")
    or not os.getenv("MISO_CONTROLLER_URL"),
    reason="Required environment variables not set (MISO_CLIENTID, MISO_CLIENTSECRET, MISO_CONTROLLER_URL)",
)
def test_validate_api_calls():
    """
    Validate API endpoints by checking they can be called.

    This test ensures the SDK can successfully call all API endpoints.
    It's an integration test that requires a running controller.
    """
    # This test is now replaced by tests/integration/test_api_endpoints.py
    # which provides comprehensive integration tests for all endpoints.
    # This placeholder test ensures the test suite doesn't break.
    pytest.skip("Use tests/integration/test_api_endpoints.py for API endpoint validation")
