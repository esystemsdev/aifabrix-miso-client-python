#!/usr/bin/env python3
"""
Test script to diagnose permission access issues.

This script checks what permissions a user has and specifically
tests for the "external-system:create" permission.
"""

import asyncio
import sys

from miso_client import MisoClient, load_config


async def test_permissions(token: str) -> None:
    """
    Test user permissions and diagnose access issues.

    Args:
        token: JWT token to test
    """
    print("=" * 80)
    print("MISO Permission Access Test")
    print("=" * 80)
    print()

    # Load configuration from .env file
    print("Loading configuration from .env...")
    try:
        config = load_config()
        print("✓ Configuration loaded successfully")
        print(f"  Controller URL: {config.controller_url}")
        print(f"  Client ID: {config.client_id}")
        print()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        print("  Make sure .env file exists with MISO_CLIENTID, MISO_CLIENTSECRET")
        sys.exit(1)

    # Initialize client
    client = MisoClient(config)
    try:
        await client.initialize()

        print("✓ Client initialized successfully")
        print()

        # Get user info
        print("Fetching user information...")
        try:
            user_info = await client.get_user(token)
            if user_info:
                print(f"✓ User ID: {user_info.id}")
                print(f"✓ Username: {user_info.username}")
                print(f"✓ Email: {user_info.email}")
            else:
                print("✗ Failed to get user information")
        except Exception as e:
            print(f"✗ Error fetching user info: {e}")
        print()

        # Get roles
        print("Fetching user roles...")
        try:
            roles = await client.get_roles(token)
            print(f"✓ Found {len(roles)} roles:")
            for role in sorted(roles):
                print(f"  - {role}")
        except Exception as e:
            print(f"✗ Error fetching roles: {e}")
            roles = []
        print()

        # Get permissions - THIS IS THE KEY FUNCTION (matches TypeScript implementation)
        print("Fetching user permissions from controller...")
        try:
            permissions = await client.get_permissions(token)
            print(f"✓ Found {len(permissions)} permissions:")
            if permissions:
                for perm in sorted(permissions):
                    print(f"  - {perm}")
            else:
                print("  (No permissions found)")
        except Exception as e:
            print(f"✗ Error fetching permissions: {e}")
            print(f"  Error type: {type(e).__name__}")
            if hasattr(e, "error_response") and e.error_response:
                print(f"  Status Code: {e.error_response.statusCode}")
                print(f"  Error Type: {e.error_response.type}")
                print(f"  Errors: {e.error_response.errors}")
                print(f"  Correlation ID: {e.error_response.correlationId}")
            import traceback

            traceback.print_exc()
            permissions = []
        print()

        # Check specific permission
        target_permission = "external-system:create"
        print(f"Checking for permission: {target_permission}")
        try:
            has_permission = await client.has_permission(token, target_permission)
            if has_permission:
                print(f"✓ User HAS permission: {target_permission}")
            else:
                print(f"✗ User DOES NOT have permission: {target_permission}")
                print()
                print("Diagnosis:")
                print(
                    f"  - The permission '{target_permission}' is not in the user's permission list"
                )
                print(f"  - User has {len(permissions)} permissions total")
                print(f"  - User has {len(roles)} roles")
                print()
                print("Possible reasons:")
                print("  1. The permission is not assigned to any of the user's roles")
                print("  2. The permission needs to be granted explicitly")
                print("  3. The user's roles need to be updated in the Miso Controller")
                print("  4. There may be environment/application context requirements")
        except Exception as e:
            print(f"✗ Error checking permission: {e}")
            # Check manually if we have permissions list
            if permissions:
                has_permission = target_permission in permissions
                if has_permission:
                    print(f"✓ Permission found in list: {target_permission}")
                else:
                    print(f"✗ Permission NOT found in list: {target_permission}")
        print()

        # Try refreshing permissions (bypass cache)
        print("Refreshing permissions (bypassing cache)...")
        try:
            refreshed_permissions = await client.refresh_permissions(token)
            print(f"✓ Refreshed: {len(refreshed_permissions)} permissions")
            if refreshed_permissions != permissions:
                print("  (Permissions changed after refresh)")
                new_perms = set(refreshed_permissions) - set(permissions)
                removed_perms = set(permissions) - set(refreshed_permissions)
                if new_perms:
                    print("  New permissions:")
                    for perm in sorted(new_perms):
                        print(f"    + {perm}")
                if removed_perms:
                    print("  Removed permissions:")
                    for perm in sorted(removed_perms):
                        print(f"    - {perm}")

            has_permission_refreshed = target_permission in refreshed_permissions
            if has_permission_refreshed:
                print(f"\n✓ After refresh: User HAS permission: {target_permission}")
            else:
                print(f"\n✗ After refresh: User DOES NOT have permission: {target_permission}")
        except Exception as e:
            print(f"✗ Error refreshing permissions: {e}")
            if hasattr(e, "error_response") and e.error_response:
                print(f"  Status Code: {e.error_response.statusCode}")
                print(f"  Error Type: {e.error_response.type}")
                print(f"  Errors: {e.error_response.errors}")

    except Exception as error:
        print(f"✗ Error: {error}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        await client.disconnect()


async def main():
    """Main entry point."""
    # Your new token
    # Long JWT token - broken into parts for readability
    token = (
        "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ6UHAzQUdwYjVNRV84bGNnbVlwdm54"
        "MlJZd2JLcGJiUXA1WG1pVWVuY2dJIn0.eyJleHAiOjE3Njg5MzExNDMsImlhdCI6MTc2ODkyOTM0Mywi"
        "anRpIjoib25ydGFjOjBmODkxNTVlLTY0N2YtNWMzNi0zNzg3LTI2MjVmNjQ2MGUwMiIsImlzcyI6Imh0"
        "dHA6Ly9sb2NhbGhvc3Q6ODE4Mi9yZWFsbXMvYWlmYWJyaXgiLCJhdWQiOiJhY2NvdW50IiwidHlwIjoi"
        "QmVhcmVyIiwiYXpwIjoibWlzby1jb250cm9sbGVyIiwic2lkIjoiNzdiZmUyMDEtZDE2MC1mMTA0LWU3"
        "YzQtOTIyOGQ5OGI1ZTI5IiwiYWxsb3dlZC1vcmlnaW5zIjpbIioiXSwicmVhbG1fYWNjZXNzIjp7InJv"
        "bGVzIjpbIm9mZmxpbmVfYWNjZXNzIiwiZGVmYXVsdC1yb2xlcy1haWZhYnJpeCIsInVtYV9hdXRob3Jp"
        "emF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNj"
        "b3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJlbWFp"
        "bCBwcm9maWxlIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsIm5hbWUiOiJBZG1pbiBVc2VyIiwicHJlZmVy"
        "cmVkX3VzZXJuYW1lIjoiYWRtaW4iLCJnaXZlbl9uYW1lIjoiQWRtaW4iLCJmYW1pbHlfbmFtZSI6IlVz"
        "ZXIiLCJlbWFpbCI6ImFkbWluQGFpZmFicml4LmFpIn0.mt1Yb4SWHP_YDNqst2On0Vsv2UtnmMCytY4M"
        "kFXelN1lB0eO6Ag-kU97gjosA74C5q873Aa_wby6J3Cyy5PJkP1tFjaqbReWcDUNWSHFqfHLTrEr91T-"
        "cO7Wj4eBrNknNvc_HUID9z2cXOQBxmMdWqXaOA6IfJv-fMSi3eUVn1HA5E7oyjuN9ofqD_0rgXPiFHFI"
        "Gc0jKTs4Z1qsRhNGQfy7Ye7ndnApG2Xt7_zztJ2syEJZlOxGSwVOu9UfqgrvIh_3EZe7GjrTZ6j7Ht9o"
        "RF2Oh1n5EAXo7EUo8QDiCVZwFlwc_TDpXUhm1g-LghazCaFX_LltxKq8ddDXGsNnMg"
    )

    await test_permissions(token)


if __name__ == "__main__":
    asyncio.run(main())
