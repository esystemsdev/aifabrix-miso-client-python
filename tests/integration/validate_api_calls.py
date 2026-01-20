#!/usr/bin/env python3
"""
Script to validate all miso-controller API calls against OpenAPI specification.
"""

import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


def fetch_openapi_spec() -> Dict:
    """Fetch and parse OpenAPI specification."""
    result = subprocess.run(
        ["curl", "-s", "http://localhost:3100/api/v1/openapi.yaml"], capture_output=True, text=True
    )
    spec_text = result.stdout

    # Extract paths from YAML (basic parsing)
    paths = {}
    current_path = None

    for line in spec_text.split("\n"):
        # Match path definitions: /api/v1/...
        path_match = re.match(r"^\s+(/api/v1/[^:]+):\s*$", line)
        if path_match:
            current_path = path_match.group(1)
            paths[current_path] = {}
            continue

        # Match HTTP methods
        method_match = re.match(r"^\s+(get|post|put|delete|patch):\s*$", line, re.IGNORECASE)
        if method_match and current_path:
            method = method_match.group(1).upper()
            paths[current_path][method] = True

    return paths


def extract_api_calls_from_codebase() -> List[Tuple[str, str, str, str]]:
    """
    Extract all API calls from the codebase.

    Returns:
        List of tuples: (file_path, line_num, method, endpoint)
    """
    # Get project root (3 levels up from tests/integration/validate_api_calls.py)
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent.parent

    api_calls = []

    # Walk through all Python files
    miso_client_dir = base_dir / "miso_client"
    for root, dirs, files in os.walk(str(miso_client_dir)):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, str(base_dir))

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract method and endpoint patterns (multiline support)
                patterns = [
                    # Pattern 1: "POST", "/api/v1/..." or 'POST', '/api/v1/...'
                    (
                        r'["\'](GET|POST|PUT|DELETE|PATCH)["\']\s*,\s*["\'](/api/v1/[^"\']+)["\']',
                        1,
                        2,
                    ),
                    # Pattern 2: client.post("/api/v1/...") or client.get("/api/v1/...")
                    (r'\.(get|post|put|delete|patch)\(["\'](/api/v1/[^"\']+)["\']', 1, 2),
                    # Pattern 3: request("POST", "/api/v1/...") - multiline
                    (
                        r'request\(\s*["\'](GET|POST|PUT|DELETE|PATCH)["\']\s*,\s*["\'](/api/v1/[^"\']+)["\']',
                        1,
                        2,
                    ),
                    # Pattern 4: authenticated_request("POST", "/api/v1/...") - multiline
                    (
                        r'authenticated_request\(\s*["\'](GET|POST|PUT|DELETE|PATCH)["\']\s*,\s*["\'](/api/v1/[^"\']+)["\']',
                        1,
                        2,
                    ),
                ]

                for pattern, method_idx, endpoint_idx in patterns:
                    for match in re.finditer(
                        pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL
                    ):
                        method = match.group(method_idx).upper()
                        endpoint = match.group(endpoint_idx)
                        # Remove query params
                        if "?" in endpoint:
                            endpoint = endpoint.split("?")[0]

                        # Find line number
                        line_num = content[: match.start()].count("\n") + 1
                        api_calls.append((rel_path, str(line_num), method, endpoint))

            except Exception as e:
                print(f"Warning: Could not read {rel_path}: {e}")
                continue

    # Remove duplicates (same file, method, endpoint) while preserving order
    seen = set()
    unique_calls = []
    for call in api_calls:
        # Use (file, method, endpoint) as key to avoid duplicates
        key = (call[0], call[2], call[3])
        if key not in seen:
            seen.add(key)
            unique_calls.append(call)

    return unique_calls


def normalize_endpoint(endpoint: str) -> str:
    """Normalize endpoint by removing query parameters."""
    if "?" in endpoint:
        endpoint = endpoint.split("?")[0]
    return endpoint


def main():
    """Main validation function."""
    print("=" * 80)
    print("MISO-CONTROLLER API CALL VALIDATION")
    print("=" * 80)

    print("\n1. Fetching OpenAPI specification...")
    try:
        paths = fetch_openapi_spec()
        print(f"   ✅ Loaded {len(paths)} endpoints from OpenAPI spec")
    except Exception as e:
        print(f"   ❌ Error fetching OpenAPI spec: {e}")
        sys.exit(1)

    print("\n2. Extracting API calls from codebase...")
    api_calls = extract_api_calls_from_codebase()
    print(f"   ✅ Found {len(api_calls)} API calls in codebase")

    # Build OpenAPI endpoint set
    openapi_endpoints: Set[Tuple[str, str]] = set()
    for path, methods in paths.items():
        for method in methods.keys():
            openapi_endpoints.add((method.upper(), normalize_endpoint(path)))

    # Validate each API call
    validated = []
    issues = []
    call_counts = defaultdict(int)

    for file_path, line_num, method, endpoint in api_calls:
        normalized_endpoint = normalize_endpoint(endpoint)
        call_key = (method, normalized_endpoint)
        call_counts[call_key] += 1

        if call_key in openapi_endpoints:
            validated.append((file_path, line_num, method, endpoint))
        else:
            # Check if endpoint exists with different method
            path_exists = normalized_endpoint in paths
            available_methods = list(paths[normalized_endpoint].keys()) if path_exists else []

            issues.append(
                {
                    "file": file_path,
                    "line": line_num,
                    "method": method,
                    "endpoint": endpoint,
                    "normalized": normalized_endpoint,
                    "path_exists": path_exists,
                    "available_methods": available_methods,
                }
            )

    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)

    print(f"\n✅ Validated: {len(validated)} API calls")
    print(f"❌ Issues: {len(issues)} API calls")

    # Group validated calls by endpoint
    if validated:
        print("\n📋 Validated API Calls (grouped by endpoint):")
        validated_by_endpoint = defaultdict(list)
        for file_path, line_num, method, endpoint in validated:
            normalized = normalize_endpoint(endpoint)
            validated_by_endpoint[(method, normalized)].append((file_path, line_num))

        for (method, endpoint), locations in sorted(validated_by_endpoint.items()):
            count = len(locations)
            print(f"  {method:6} {endpoint:50} ({count} call{'s' if count > 1 else ''})")
            if count <= 3:  # Show locations if few calls
                for file_path, line_num in locations:
                    print(f"           → {file_path}:{line_num}")

    # Print issues
    if issues:
        print("\n" + "=" * 80)
        print("❌ ISSUES FOUND")
        print("=" * 80)

        for issue in issues:
            print(f"\n  {issue['method']:6} {issue['endpoint']}")
            print(f"         File: {issue['file']}:{issue['line']}")

            if issue["path_exists"]:
                print(f"         ⚠️  Endpoint exists but method '{issue['method']}' not available")
                print(f"         Available methods: {', '.join(issue['available_methods'])}")
            else:
                print("         ❌ Endpoint not found in OpenAPI spec")
                # Check for similar paths
                similar = [
                    p
                    for p in paths.keys()
                    if issue["normalized"].startswith(p.rstrip("/"))
                    or p.startswith(issue["normalized"].rstrip("/"))
                ]
                if similar:
                    print(f"         Similar paths found: {similar[:3]}")

    # Show all OpenAPI endpoints for reference
    print("\n" + "=" * 80)
    print("AVAILABLE ENDPOINTS IN OPENAPI SPEC")
    print("=" * 80)
    print(f"\nTotal: {len(paths)} endpoints\n")

    # Group by prefix
    by_prefix = defaultdict(list)
    for path in sorted(paths.keys()):
        prefix = path.split("/")[3] if len(path.split("/")) > 3 else "other"
        by_prefix[prefix].append((path, list(paths[path].keys())))

    for prefix in sorted(by_prefix.keys()):
        print(f"\n{prefix.upper()}:")
        for path, methods in by_prefix[prefix]:
            print(f"  {path:60} {sorted(methods)}")

    # Return success status
    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
