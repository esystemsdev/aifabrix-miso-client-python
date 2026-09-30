"""Real encryption round trips for a registered test app, in both runtime modes.

Explicitly invoked only. Requires MISO_ENCRYPTION_E2E_KEY; the ordinary test
ENCRYPTION_KEY is synthetic and must never be used for a live controller.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Callable
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from miso_client import MisoClient, init_secrets
from miso_client.models.config import MisoClientConfig
from miso_client.utils.bootstrap_runtime import SecretsRuntime


@pytest_asyncio.fixture(params=["local", "client-credentials"])
async def encryption_client(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> AsyncIterator[MisoClient]:
    """Use real credentials and disable cache so both endpoints must be called."""
    caplog.set_level(logging.CRITICAL)
    load_dotenv(override=False)
    required = (
        "MISO_CONTROLLER_URL",
        "MISO_CLIENTID",
        "MISO_CLIENTSECRET",
        "MISO_ENCRYPTION_E2E_KEY",
    )
    for name in required:
        if not os.environ.get(name):
            pytest.fail(f"Missing live encryption setting: {name}", pytrace=False)
    runtime: SecretsRuntime | None = None
    client: MisoClient | None = None
    ready = False
    try:
        if request.param == "client-credentials":
            monkeypatch.setenv("MISO_AUTH_MODE", "client-credentials")
            runtime = await init_secrets()
            config = runtime.client.config.model_copy(
                update={
                    "encryption_key": os.environ["MISO_ENCRYPTION_E2E_KEY"],
                    "cache": {"encryptionCacheTTL": 0},
                }
            )
        else:
            config = MisoClientConfig(
                controller_url=os.environ["MISO_CONTROLLER_URL"],
                client_id=os.environ["MISO_CLIENTID"],
                client_secret=os.environ["MISO_CLIENTSECRET"],
                encryption_key=os.environ["MISO_ENCRYPTION_E2E_KEY"],
                cache={"encryptionCacheTTL": 0},
            )
        client = MisoClient(config)
        await client.initialize()
        ready = True
    except Exception:
        pass  # Never print credentials or a raw live controller error body.
    try:
        if not ready or client is None:
            pytest.fail("Live encryption client initialization failed.", pytrace=False)
        yield client
    finally:
        if client is not None:
            await client.disconnect()
        if runtime is not None:
            await runtime.close()


async def test_live_encrypt_decrypt_roundtrip(
    encryption_client: MisoClient, record_property: Callable[[str, object], None]
) -> None:
    """Exercise both real endpoints through the public encryption service."""
    traffic: list[tuple[str, int]] = []
    correlation = str(uuid4())

    async def observe(response: httpx.Response) -> None:
        traffic.append((response.request.url.path.rsplit("/", 1)[-1], response.status_code))

    internal = encryption_client.http_client.get_internal_client()
    await internal._initialize_client()
    assert internal.client is not None
    internal.client.headers["x-correlation-id"] = correlation
    internal.client.event_hooks["response"].append(observe)
    parameter = "sdk-smoke-" + uuid4().hex
    plaintext = "throwaway-" + uuid4().hex
    matched = False
    try:
        encrypted = await asyncio.wait_for(
            encryption_client.encryption.encrypt(plaintext, parameter), timeout=45
        )
        decrypted = await asyncio.wait_for(
            encryption_client.encryption.decrypt(encrypted.value, parameter), timeout=45
        )
        matched = decrypted == plaintext
    except Exception:
        pass  # Safe result below includes counts/statuses, never secret material.
    record_property("correlation_id", correlation)
    record_property("traffic", traffic)
    assert matched, f"Encryption round trip failed; correlation={correlation}; traffic={traffic}"
    assert [path for path, _ in traffic] == ["encrypt", "decrypt"]
    assert all(200 <= status < 300 for _, status in traffic)
