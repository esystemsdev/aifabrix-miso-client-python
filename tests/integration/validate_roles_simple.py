#!/usr/bin/env python3
"""
Simple script to validate user roles and permissions count.
"""

import asyncio
import sys

from miso_client import MisoClient, load_config
from miso_client.errors import MisoClientError
from miso_client.utils.jwt_tools import decode_token, extract_user_id


def _print_error_response(error: Exception) -> bool:
    """Print structured error response when available."""
    if not isinstance(error, MisoClientError) or error.error_response is None:
        return False
    print(f"   Status: {error.error_response.statusCode}")
    print(f"   Type: {error.error_response.type}")
    print(f"   Errors: {error.error_response.errors}")
    return True


async def main() -> None:
    """Main validation function."""
    if len(sys.argv) < 2:
        print("Usage: python tests/integration/validate_roles_simple.py <JWT_TOKEN>")
        sys.exit(1)

    token = sys.argv[1]

    # Decode token
    decoded = decode_token(token)
    if not decoded:
        print("❌ Failed to decode JWT token")
        return

    user_id = extract_user_id(token)
    email = decoded.get("email", "N/A")
    username = decoded.get("preferred_username", "N/A")

    print("Token Info:")
    print(f"  User ID: {user_id}")
    print(f"  Email: {email}")
    print(f"  Username: {username}")
    print()

    # Initialize client
    try:
        config = load_config()
        client = MisoClient(config)
        await client.initialize()
        print(f"Controller URL: {config.controller_url}")
        print()
    except Exception as error:
        print(f"❌ Failed to initialize: {error}")
        return

    # Validate token
    try:
        is_valid = await client.validate_token(token)
        if not is_valid:
            print("❌ Token is invalid")
            return
        print("✅ Token is valid")
        print()
    except Exception as error:
        print(f"❌ Token validation error: {error}")
        return

    # Get roles
    print("Fetching roles...")
    roles = []
    try:
        roles = await client.get_roles(token)
    except Exception as api_error:
        print(f"   Error fetching roles: {api_error}")
        _print_error_response(api_error)

    if not roles:
        print("   ⚠️  No roles found with any environment")

    print(f"✅ Roles: {len(roles)}")
    if roles:
        print(f"   Sample: {', '.join(roles[:5])}")
    print()

    # Get permissions
    print("Fetching permissions...")
    permissions = []
    try:
        permissions = await client.get_permissions(token)
    except Exception as api_error:
        print(f"   Error fetching permissions: {api_error}")
        if _print_error_response(api_error):
            if isinstance(api_error, MisoClientError) and api_error.error_response is not None:
                print(f"   Correlation ID: {api_error.error_response.correlationId}")

    if not permissions:
        print("   ⚠️  No permissions found with any environment")

    print(f"✅ Permissions: {len(permissions)}")
    print("   Expected: 106")
    if len(permissions) == 106:
        print("   ✅ Count matches!")
    else:
        print(f"   ⚠️  Mismatch! Got {len(permissions)}, expected 106")

    if permissions:
        print(f"   Sample: {', '.join(permissions[:5])}")
    print()

    # Summary
    print("=" * 60)
    print(f"SUMMARY: {len(roles)} roles, {len(permissions)} permissions")
    print("=" * 60)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
