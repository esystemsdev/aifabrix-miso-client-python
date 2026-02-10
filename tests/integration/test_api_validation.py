"""
API Test Coverage Validation Script.

Scans all API methods in miso_client/api/ and checks for corresponding integration tests.
Reports coverage percentage and lists untested methods.

Usage:
    python -m pytest tests/integration/test_api_validation.py -v
    Or run directly: python tests/integration/test_api_validation.py
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest


def _find_api_dir() -> Path:
    """Find miso_client/api directory from this file or cwd."""
    # Pytest often runs with cwd = project root
    cwd_api = Path.cwd() / "miso_client" / "api"
    if cwd_api.is_dir():
        return cwd_api
    # Walk up from this file: tests/integration/test_api_validation.py -> project_root/miso_client/api
    start = Path(__file__).resolve().parent
    for _ in range(5):
        api_dir = start / "miso_client" / "api"
        if api_dir.is_dir():
            return api_dir
        parent = start.parent
        if parent == start:
            break
        start = parent
    return Path.cwd() / "miso_client" / "api"


def get_api_methods() -> Dict[str, List[str]]:
    """
    Scan miso_client/api/ directory and extract all API methods.

    Returns:
        Dictionary mapping API class names to list of method names
    """
    api_dir = _find_api_dir()
    api_methods: Dict[str, List[str]] = {}

    # API files to scan (excluding __init__.py and types/)
    api_files = [
        "auth_api.py",
        "logs_api.py",
        "roles_api.py",
        "permissions_api.py",
    ]

    for api_file in api_files:
        file_path = api_dir / api_file
        if not file_path.exists():
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)

        # Find the API class (include both sync and async methods)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                if class_name.endswith("Api"):
                    methods = []
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            # Skip private methods and __init__
                            if not item.name.startswith("_") and item.name != "__init__":
                                methods.append(item.name)
                    if methods:
                        api_methods[class_name] = methods

    return api_methods


def get_test_methods() -> Set[str]:
    """
    Scan test_api_endpoints.py and extract all test method names.

    Returns:
        Set of test method names
    """
    test_file = Path(__file__).resolve().parent / "test_api_endpoints.py"
    if not test_file.exists():
        return set()

    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all test methods using regex
    test_methods = set()
    pattern = r"async def (test_\w+)"
    matches = re.findall(pattern, content)
    test_methods.update(matches)

    # Also find sync test methods
    pattern = r"def (test_\w+)"
    matches = re.findall(pattern, content)
    test_methods.update(matches)

    return test_methods


def map_test_to_api_methods(test_name: str) -> List[Tuple[str, str]]:
    """
    Map test method name to one or more (API class, method) pairs.

    One test can cover multiple API classes (e.g. AuthApi and RolesApi both have get_roles).

    Args:
        test_name: Test method name (e.g., "test_get_roles")

    Returns:
        List of (api_class_name, api_method_name) pairs covered by this test
    """
    # Mapping: test name -> list of (ApiClass, method) covered
    test_to_api_map: Dict[str, List[Tuple[str, str]]] = {
        # AuthApi methods
        "test_login_initiation": [("AuthApi", "login")],
        "test_validate_token": [("AuthApi", "validate_token")],
        "test_get_user_info": [("AuthApi", "get_user")],
        "test_logout": [("AuthApi", "logout")],
        "test_refresh_token": [("AuthApi", "refresh_token")],
        "test_initiate_device_code": [("AuthApi", "initiate_device_code")],
        "test_poll_device_code_token": [("AuthApi", "poll_device_code_token")],
        "test_refresh_device_code_token": [("AuthApi", "refresh_device_code_token")],
        "test_get_roles": [("AuthApi", "get_roles"), ("RolesApi", "get_roles")],
        "test_refresh_roles": [("AuthApi", "refresh_roles"), ("RolesApi", "refresh_roles")],
        "test_get_permissions": [
            ("AuthApi", "get_permissions"),
            ("PermissionsApi", "get_permissions"),
        ],
        "test_refresh_permissions": [
            ("AuthApi", "refresh_permissions"),
            ("PermissionsApi", "refresh_permissions"),
        ],
        # LogsApi methods
        "test_create_error_log": [("LogsApi", "send_log")],
        "test_create_general_log": [("LogsApi", "send_log")],
        "test_create_audit_log": [("LogsApi", "send_log")],
        "test_create_batch_logs": [("LogsApi", "send_batch_logs")],
        "test_list_general_logs": [("LogsApi", "list_general_logs")],
        "test_list_audit_logs": [("LogsApi", "list_audit_logs")],
        "test_list_job_logs": [("LogsApi", "list_job_logs")],
        "test_get_job_log": [("LogsApi", "get_job_log")],
        "test_get_logs_stats_summary": [("LogsApi", "get_stats_summary")],
        "test_get_logs_stats_errors": [("LogsApi", "get_stats_errors")],
        "test_get_logs_stats_users": [("LogsApi", "get_stats_users")],
        "test_get_logs_stats_applications": [("LogsApi", "get_stats_applications")],
        "test_export_logs_json": [("LogsApi", "export_logs")],
        "test_export_logs_csv": [("LogsApi", "export_logs")],
    }
    return test_to_api_map.get(test_name, [])


def calculate_coverage() -> Tuple[Dict[str, Dict[str, bool]], float]:
    """
    Calculate API method test coverage.

    Returns:
        Tuple of (coverage_map, coverage_percentage)
        coverage_map: Dict mapping API class to dict of method -> is_tested
    """
    api_methods = get_api_methods()
    test_methods = get_test_methods()

    coverage_map: Dict[str, Dict[str, bool]] = {}
    total_methods = 0
    tested_methods = 0

    # Build set of (api_class, method) pairs covered by any test
    tested_pairs: Set[Tuple[str, str]] = set()
    for test_name in test_methods:
        for api_class, method in map_test_to_api_methods(test_name):
            tested_pairs.add((api_class, method))

    for api_class, methods in api_methods.items():
        coverage_map[api_class] = {}
        for method in methods:
            total_methods += 1
            is_tested = (api_class, method) in tested_pairs
            coverage_map[api_class][method] = is_tested
            if is_tested:
                tested_methods += 1

    coverage_percentage = (tested_methods / total_methods * 100) if total_methods > 0 else 0.0

    return coverage_map, coverage_percentage


def test_api_coverage():
    """
    Test that validates API method coverage.

    This test will fail if coverage is below 100%.
    """
    coverage_map, coverage_percentage = calculate_coverage()

    # Print coverage report
    print("\n" + "=" * 80)
    print("API Test Coverage Report")
    print("=" * 80)
    print(f"\nOverall Coverage: {coverage_percentage:.1f}%\n")

    untested_methods: List[Tuple[str, str]] = []

    for api_class, methods in coverage_map.items():
        print(f"{api_class}:")
        for method, is_tested in methods.items():
            status = "✅" if is_tested else "❌"
            print(f"  {status} {method}")
            if not is_tested:
                untested_methods.append((api_class, method))
        print()

    if untested_methods:
        print("\nUntested Methods:")
        for api_class, method in untested_methods:
            print(f"  - {api_class}.{method}()")
        print()

    print("=" * 80)

    # Skip if no API methods were found (e.g. wrong cwd or package not installed)
    if not coverage_map:
        pytest.skip(
            "No API methods found (api_dir may be wrong). "
            "Run from project root: pytest tests/integration/test_api_validation.py"
        )

    # Assert 100% coverage
    assert coverage_percentage == 100.0, (
        f"API test coverage is {coverage_percentage:.1f}%, expected 100%. "
        f"Untested: {len(untested_methods)}"
    )


if __name__ == "__main__":
    """Run coverage validation directly."""
    coverage_map, coverage_percentage = calculate_coverage()

    print("\n" + "=" * 80)
    print("API Test Coverage Report")
    print("=" * 80)
    print(f"\nOverall Coverage: {coverage_percentage:.1f}%\n")

    untested_methods: List[Tuple[str, str]] = []

    for api_class, methods in coverage_map.items():
        print(f"{api_class}:")
        for method, is_tested in methods.items():
            status = "✅" if is_tested else "❌"
            print(f"  {status} {method}")
            if not is_tested:
                untested_methods.append((api_class, method))
        print()

    if untested_methods:
        print("\nUntested Methods:")
        for api_class, method in untested_methods:
            print(f"  - {api_class}.{method}()")
        print()
    else:
        print("\n✅ All API methods have integration tests!\n")

    print("=" * 80)

    # Exit with error code if coverage is not 100%
    if coverage_percentage < 100.0:
        exit(1)
    else:
        exit(0)
