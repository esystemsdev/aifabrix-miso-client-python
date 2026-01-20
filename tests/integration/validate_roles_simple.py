#!/usr/bin/env python3
"""
Simple script to validate user roles and permissions count.
"""

import asyncio
import sys

from miso_client import MisoClient, load_config
from miso_client.utils.jwt_tools import decode_token, extract_user_id


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

    # Get roles - try with environment parameter using service method
    print("Fetching roles...")
    roles = []
    # Try common environment values
    environments_to_try = ["miso", "dev", "tst", "pro"]

    for env in environments_to_try:
        try:
            # Use service method with environment parameter
            roles = await client.get_roles(token, environment=env)
            if roles:
                print(f"   ✅ Success with environment='{env}' using service method")
                break
        except Exception as api_error:
            error_msg = str(api_error)
            print(f"   Error with environment='{env}': {error_msg}")
            if hasattr(api_error, "error_response") and api_error.error_response:
                print(f"   Status: {api_error.error_response.statusCode}")
                print(f"   Type: {api_error.error_response.type}")
                print(f"   Errors: {api_error.error_response.errors}")
                if api_error.error_response.statusCode == 400:
                    # Try next environment
                    continue
                else:
                    break

    if not roles:
        print("   ⚠️  No roles found with any environment")

    print(f"✅ Roles: {len(roles)}")
    if roles:
        print(f"   Sample: {', '.join(roles[:5])}")
    print()

    # Get permissions - try with environment parameter using service method
    print("Fetching permissions...")
    permissions = []
    # Try common environment values
    for env in environments_to_try:
        try:
            # Use service method with environment parameter
            permissions = await client.get_permissions(token, environment=env)
            if permissions:
                print(f"   ✅ Success with environment='{env}' using service method")
                break
        except Exception as api_error:
            error_msg = str(api_error)
            print(f"   Error with environment='{env}': {error_msg}")
            if hasattr(api_error, "error_response") and api_error.error_response:
                print(f"   Status: {api_error.error_response.statusCode}")
                print(f"   Type: {api_error.error_response.type}")
                print(f"   Errors: {api_error.error_response.errors}")
                print(f"   Correlation ID: {api_error.error_response.correlationId}")
                if api_error.error_response.statusCode == 400:
                    # Try next environment
                    continue
                else:
                    break

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
