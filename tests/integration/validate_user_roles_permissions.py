#!/usr/bin/env python3
"""
Script to validate user roles and permissions from a JWT token.

This script:
1. Decodes the JWT token to extract user information
2. Fetches roles and permissions from the Miso Controller
3. Displays counts and details
"""

import asyncio
import json
import sys

from miso_client import MisoClient, load_config
from miso_client.utils.jwt_tools import decode_token, extract_user_id


async def validate_user_roles_permissions(token: str) -> None:
    """
    Validate user roles and permissions.

    Args:
        token: JWT token string
    """
    print("=" * 80)
    print("USER ROLES AND PERMISSIONS VALIDATION")
    print("=" * 80)
    print()

    # Step 1: Decode JWT token
    print("Step 1: Decoding JWT token...")
    decoded = decode_token(token)
    if not decoded:
        print("❌ ERROR: Failed to decode JWT token")
        return

    user_id = extract_user_id(token)
    print("✅ Token decoded successfully")
    print(f"   User ID: {user_id}")
    print(f"   Email: {decoded.get('email', 'N/A')}")
    print(f"   Name: {decoded.get('name', 'N/A')}")
    print(f"   Username: {decoded.get('preferred_username', 'N/A')}")
    print()

    # Extract roles from token (if present)
    token_roles = []
    if "realm_access" in decoded and "roles" in decoded["realm_access"]:
        token_roles = decoded["realm_access"]["roles"]
    elif "roles" in decoded:
        token_roles = decoded["roles"]

    if token_roles:
        print(f"   Roles in token: {len(token_roles)}")
        print(f"   Token roles: {', '.join(token_roles[:5])}")
        if len(token_roles) > 5:
            print(f"   ... and {len(token_roles) - 5} more")
    print()

    # Step 2: Initialize MisoClient
    print("Step 2: Initializing MisoClient...")
    try:
        config = load_config()
        client = MisoClient(config)
        await client.initialize()
        print("✅ MisoClient initialized successfully")
        print(f"   Controller URL: {config.controller_url}")
        print(f"   Redis connected: {client.is_redis_connected()}")
        print()
    except Exception as error:
        print(f"❌ ERROR: Failed to initialize MisoClient: {error}")
        return

    # Step 3: Validate token
    print("Step 3: Validating token with controller...")
    try:
        is_valid = await client.validate_token(token)
        if is_valid:
            print("✅ Token is valid")
        else:
            print("❌ Token validation failed")
            return
        print()
    except Exception as error:
        print(f"❌ ERROR: Token validation error: {error}")
        print(f"   Error type: {type(error).__name__}")
        if hasattr(error, "error_response"):
            print(f"   Error response: {error.error_response}")
        return

    # Step 4: Get user info
    print("Step 4: Fetching user information...")
    try:
        user_info = await client.get_user(token)
        if user_info:
            print("✅ User information retrieved")
            print(f"   User ID: {user_info.id}")
            print(f"   Email: {user_info.email}")
            print(f"   Username: {user_info.username}")
        else:
            print("⚠️  User information not available")
        print()
    except Exception as error:
        print(f"⚠️  Warning: Failed to get user info: {error}")
        print()

    # Step 5: Get roles
    print("Step 5: Fetching user roles...")
    try:
        # Try direct API call to see raw response
        try:
            raw_roles_response = await client.http_client.authenticated_request(
                "GET", "/api/v1/auth/roles", token
            )
            print(f"   Raw API response: {json.dumps(raw_roles_response, indent=2)}")
        except Exception as api_error:
            print(f"   ⚠️  Direct API call error: {api_error}")

        roles = await client.get_roles(token)
        print(f"✅ Roles retrieved: {len(roles)} roles")
        if roles:
            print(f"   Roles: {', '.join(roles[:10])}")
            if len(roles) > 10:
                print(f"   ... and {len(roles) - 10} more")
        else:
            print("   ⚠️  No roles found")
        print()
    except Exception as error:
        print(f"❌ ERROR: Failed to get roles: {error}")
        print(f"   Error type: {type(error).__name__}")
        if hasattr(error, "error_response"):
            print(f"   Error response: {error.error_response}")
        roles = []

    # Step 6: Get permissions
    print("Step 6: Fetching user permissions...")
    try:
        # Try direct API call to see raw response
        try:
            raw_permissions_response = await client.http_client.authenticated_request(
                "GET", "/api/v1/auth/permissions", token
            )
            print(f"   Raw API response: {json.dumps(raw_permissions_response, indent=2)}")
        except Exception as api_error:
            print(f"   ⚠️  Direct API call error: {api_error}")
            if hasattr(api_error, "error_response"):
                print(f"   Error response: {api_error.error_response}")

        permissions = await client.get_permissions(token)
        print(f"✅ Permissions retrieved: {len(permissions)} permissions")
        if permissions:
            print("   Expected: 106 permissions")
            print(f"   Actual: {len(permissions)} permissions")
            if len(permissions) == 106:
                print("   ✅ Permission count matches expected value")
            else:
                print(f"   ⚠️  Permission count mismatch! Expected 106, got {len(permissions)}")
            print()
            print("   First 10 permissions:")
            for i, perm in enumerate(permissions[:10], 1):
                print(f"   {i}. {perm}")
            if len(permissions) > 10:
                print(f"   ... and {len(permissions) - 10} more")
        else:
            print("   ❌ No permissions found")
        print()
    except Exception as error:
        print(f"❌ ERROR: Failed to get permissions: {error}")
        print(f"   Error type: {type(error).__name__}")
        if hasattr(error, "error_response"):
            print(f"   Error response: {error.error_response}")
            if error.error_response:
                print(f"   Status Code: {error.error_response.statusCode}")
                print(f"   Error Type: {error.error_response.type}")
                print(f"   Errors: {error.error_response.errors}")
                print(f"   Correlation ID: {error.error_response.correlationId}")
        permissions = []

    # Step 7: Try refresh to bypass cache
    print("Step 7: Refreshing permissions (bypass cache)...")
    try:
        refreshed_permissions = await client.refresh_permissions(token)
        print(f"✅ Refreshed permissions: {len(refreshed_permissions)} permissions")
        if len(refreshed_permissions) != len(permissions):
            print("   ⚠️  Permission count changed after refresh!")
            print(f"   Before refresh: {len(permissions)}")
            print(f"   After refresh: {len(refreshed_permissions)}")
        print()
    except Exception as error:
        print(f"❌ ERROR: Failed to refresh permissions: {error}")
        print(f"   Error type: {type(error).__name__}")
        if hasattr(error, "error_response"):
            print(f"   Error response: {error.error_response}")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"User ID: {user_id}")
    print(f"Roles: {len(roles)}")
    print(f"Permissions: {len(permissions)}")
    if len(permissions) != 106:
        print(f"⚠️  WARNING: Expected 106 permissions, but got {len(permissions)}")
    print("=" * 80)

    # Cleanup
    await client.disconnect()


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python tests/integration/validate_user_roles_permissions.py <JWT_TOKEN>")
        print()
        print("Example:")
        print(
            "  python tests/integration/validate_user_roles_permissions.py eyJhbGciOiJSUzI1NiIs..."
        )
        sys.exit(1)

    token = sys.argv[1]
    asyncio.run(validate_user_roles_permissions(token))


if __name__ == "__main__":
    main()
