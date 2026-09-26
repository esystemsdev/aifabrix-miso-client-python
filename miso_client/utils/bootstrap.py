"""Opt-in initialization with a legacy-compatible default and client-credential bootstrap."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx

from ..models.bootstrap import BootstrapError
from ..models.config import MisoClientConfig
from .bootstrap_credentials import validate_settings
from .bootstrap_runtime import SecretsRuntime
from .bootstrap_transport import BrokerTransport
from .config_loader import load_config


async def _initialize_local(runtime: SecretsRuntime) -> None:
    """Preserve the original local loader and token endpoint behavior."""
    config = load_config()
    config.runtime_guard = runtime.ensure_active
    await runtime.initialize_client(config, dict(os.environ))


async def _initialize_credentials(
    runtime: SecretsRuntime,
    http_client: Optional[httpx.AsyncClient],
) -> None:
    """Bootstrap before constructing any normal SDK services."""
    url = os.environ.get("MISO_CONTROLLER_URL", "")
    endpoint = validate_settings(url)
    runtime.attach_transport(
        BrokerTransport(
            endpoint,
            os.environ.get("MISO_CLIENTID", ""),
            os.environ.get("MISO_CLIENTSECRET", ""),
            http_client,
        )
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
    http_client: Optional[httpx.AsyncClient] = None,
) -> SecretsRuntime:
    """Initialize local secrets or an explicitly enabled client-credential runtime.

    Args:
        http_client: Optional broker client with trust_env=False and no event hooks; caller-owned.

    Returns:
        An initialized client and secret accessors with awaitable close.

    Raises:
        BootstrapError: Configuration, authentication or initialization failed.
    """
    mode = os.environ.get("MISO_AUTH_MODE", "local")
    if mode not in ("local", "client-credentials"):
        raise BootstrapError("invalid-auth-mode")
    return await _initialize_runtime(mode, http_client)


async def _initialize_runtime(
    mode: str,
    http_client: Optional[httpx.AsyncClient],
) -> SecretsRuntime:
    """Clean up partially initialized runtimes without retaining raw errors."""
    runtime = SecretsRuntime()
    failure: Optional[BootstrapError] = None
    try:
        if mode == "local":
            await _initialize_local(runtime)
        else:
            await _initialize_credentials(runtime, http_client)
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
