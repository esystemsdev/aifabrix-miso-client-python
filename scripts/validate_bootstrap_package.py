"""Installed-wheel smoke: local initialization without Azure imports or network.

Run using the wheel's interpreter in isolated mode:
    python -I /absolute/path/scripts/validate_bootstrap_package.py [--azure]
"""

import asyncio
import builtins
import importlib.metadata
import json
import os
import sys
from unittest.mock import patch


def guarded_import(name, *args, **kwargs):
    """Reject optional Azure imports during base/local initialization."""
    if name == "azure" or name.startswith("azure."):
        raise AssertionError("Local initialization imported Azure")
    return original_import(name, *args, **kwargs)


original_import = builtins.__import__


async def main():
    """Prove both older-controller-compatible local behavior and optional imports."""
    os.environ.clear()
    os.environ.update(
        MISO_AUTH_MODE="local",
        MISO_CLIENTID="smoke-client",
        MISO_CLIENTSECRET="smoke-secret",
        DATABASE_URL="smoke-url",
    )
    with patch("builtins.__import__", side_effect=guarded_import):
        from miso_client import MisoClientConfig, init_secrets

        with patch("miso_client.utils.config_loader._load_dotenv_if_available"), patch(
            "httpx.AsyncClient", side_effect=AssertionError("Unexpected network client")
        ):
            runtime = await init_secrets()
            assert runtime.secrets.require("DATABASE_URL") == "smoke-url"
            assert runtime.client.config.client_id == "smoke-client"
            assert (
                "application_token_provider"
                not in MisoClientConfig.model_json_schema()["properties"]
            )
            await runtime.close()
    result = {"python": sys.version.split()[0], "local": "passed"}
    if "--azure" in sys.argv:
        from azure.identity.aio import ManagedIdentityCredential

        credential = ManagedIdentityCredential(retry_total=0, logging_enable=False)
        await credential.close()
        result["azure-identity"] = importlib.metadata.version("azure-identity")
        result["aiohttp"] = importlib.metadata.version("aiohttp")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
