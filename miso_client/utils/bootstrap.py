"""Opt-in initialization with a legacy-compatible default and isolated Azure mode."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx

from ..models.bootstrap import BootstrapError, IdentityTokenProvider
from ..models.config import MisoClientConfig
from .bootstrap_identity import AzureIdentityProvider
from .bootstrap_runtime import SecretsRuntime
from .bootstrap_transport import BrokerTransport, validate_settings
from .config_loader import load_config


async def _initialize_local(runtime: SecretsRuntime) -> None:
    """Preserve the original local loader and token endpoint behavior."""
    config = load_config()
    config.runtime_guard = runtime.ensure_active
    await runtime.initialize_client(config, dict(os.environ))


async def _initialize_azure(
    runtime: SecretsRuntime,
    provider: Optional[IdentityTokenProvider],
    http_client: Optional[httpx.AsyncClient],
) -> None:
    """Bootstrap before constructing any normal SDK services."""
    url = os.environ.get("MISO_CONTROLLER_URL", "")
    audience = os.environ.get("MISO_BOOTSTRAP_AUDIENCE", "")
    endpoint = validate_settings(url, audience)
    identity_close = None
    if provider is None:
        owned = AzureIdentityProvider(os.environ.get("AZURE_CLIENT_ID") or None)
        identity_close = owned.close
        provider = owned
    runtime.attach_transport(
        BrokerTransport(endpoint, audience, provider, http_client), identity_close
    )
    await runtime.refresh()
    config = MisoClientConfig(
        controller_url=url,
        client_id=runtime.client_identifier,
        application_token_provider=runtime,
        runtime_guard=runtime.ensure_active,
    )
    await runtime.initialize_client(config)
    runtime.start_refresh()


async def init_secrets(
    *,
    token_provider: Optional[IdentityTokenProvider] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> SecretsRuntime:
    """Initialize local secrets or an explicitly enabled managed-identity runtime.

    Args:
        token_provider: Optional Azure test/host provider; remains caller-owned.
        http_client: Optional isolated broker HTTP client; remains caller-owned.

    Returns:
        An initialized client and secret accessors with awaitable close.

    Raises:
        BootstrapError: Configuration, authentication or initialization failed.
    """
    mode = os.environ.get("MISO_AUTH_MODE", "local")
    if mode not in ("local", "azure-managed-identity"):
        raise BootstrapError("invalid-auth-mode")
    return await _initialize_runtime(mode, token_provider, http_client)


async def _initialize_runtime(
    mode: str,
    token_provider: Optional[IdentityTokenProvider],
    http_client: Optional[httpx.AsyncClient],
) -> SecretsRuntime:
    """Clean up partially initialized runtimes without retaining raw errors."""
    runtime = SecretsRuntime()
    failure: Optional[BootstrapError] = None
    try:
        if mode == "local":
            await _initialize_local(runtime)
        else:
            await _initialize_azure(runtime, token_provider, http_client)
        return runtime
    except asyncio.CancelledError:
        await runtime.close()
        raise
    except BootstrapError as error:
        failure = BootstrapError(error.code, error.status_code)
    except Exception:
        failure = BootstrapError("initialization-failed")
    await runtime.close()
    raise failure
