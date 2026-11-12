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

from miso_client import EncryptionError, MisoClient, init_secrets
from miso_client.models.config import LogEntry, MisoClientConfig
from miso_client.utils.bootstrap_runtime import SecretsRuntime


@pytest_asyncio.fixture(params=["local", "client-credentials"])
async def encryption_client(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    captured_log_entries: list[LogEntry],
) -> AsyncIterator[MisoClient]:
    """Use real credentials and disable cache so both endpoints must be called."""
    caplog.set_level(logging.DEBUG, logger="miso_client.services.encryption")
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
                    "log_level": "debug",
                    "emit_events": True,
                }
            )
        else:
            config = MisoClientConfig(
                controller_url=os.environ["MISO_CONTROLLER_URL"],
                client_id=os.environ["MISO_CLIENTID"],
                client_secret=os.environ["MISO_CLIENTSECRET"],
                encryption_key=os.environ["MISO_ENCRYPTION_E2E_KEY"],
                cache={"encryptionCacheTTL": 0},
                log_level="debug",
                emit_events=True,
            )
        client = MisoClient(config)
        await client.initialize()
        client.logger.on(captured_log_entries.append)
        ready = True
    except Exception:
        pass  # Never print credentials or a raw live controller error body.
    try:
        if not ready or client is None:
            caplog.clear()
            captured_log_entries.clear()
            pytest.fail("Live encryption client initialization failed.", pytrace=False)
        yield client
    finally:
        if client is not None:
            await client.disconnect()
        if runtime is not None:
            await runtime.close()


@pytest.fixture
def captured_log_entries() -> list[LogEntry]:
    """Collect final SDK log entries without sending them to shared sinks."""
    return []


async def test_live_encrypt_decrypt_roundtrip(
    encryption_client: MisoClient,
    captured_log_entries: list[LogEntry],
    caplog: pytest.LogCaptureFixture,
    record_property: Callable[[str, object], None],
) -> None:
    """Exercise real endpoints and prove final debug records contain no markers."""
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
    failure_value = "enc://v1:invalid-" + uuid4().hex
    matched = False
    failure_observed = False
    encrypted_value: str | None = None
    storage: str | None = None
    try:
        encrypted = await asyncio.wait_for(
            encryption_client.encryption.encrypt(plaintext, parameter), timeout=45
        )
        encrypted_value = encrypted.value
        storage = encrypted.storage
        decrypted = await asyncio.wait_for(
            encryption_client.encryption.decrypt(encrypted.value, parameter), timeout=45
        )
        matched = decrypted == plaintext
    except Exception:
        pass  # Safe result below includes counts/statuses, never secret material.
    try:
        await asyncio.wait_for(
            encryption_client.encryption.decrypt(failure_value, parameter), timeout=45
        )
    except EncryptionError:
        failure_observed = True
    except Exception:
        pass
    await encryption_client.http_client._wait_for_logging_tasks(timeout=2.0)

    serialized_logs = (
        "\n".join(entry.model_dump_json() for entry in captured_log_entries) + caplog.text
    )
    markers = (
        plaintext,
        parameter,
        failure_value,
        os.environ["MISO_CLIENTSECRET"],
        os.environ["MISO_ENCRYPTION_E2E_KEY"],
        encrypted_value or "",
    )
    secrecy_ok = all(not marker or marker not in serialized_logs for marker in markers)
    log_levels = sorted({entry.level for entry in captured_log_entries})
    safe_log_events = len(captured_log_entries)
    cleanup_status = (
        "not-required-local"
        if storage == "local"
        else "pending-no-supported-controller-delete-route"
    )
    record_property("correlation_id", correlation)
    record_property("traffic", traffic)
    record_property("log_levels", log_levels)
    record_property("safe_log_events", safe_log_events)
    record_property("failure_probe", failure_observed)
    record_property("storage", storage or "unknown")
    record_property("cleanup_status", cleanup_status)
    captured_log_entries.clear()
    caplog.clear()

    assert encryption_client.config.log_level == "debug"
    assert encryption_client.config.emit_events is True
    assert matched, f"Encryption round trip failed; correlation={correlation}; traffic={traffic}"
    assert (
        failure_observed
    ), f"Failure probe did not fail; correlation={correlation}; traffic={traffic}"
    assert [path for path, _ in traffic[:2]] == ["encrypt", "decrypt"]
    assert all(200 <= status < 300 for _, status in traffic[:2])
    assert traffic[-1][0] == "decrypt"
    assert traffic[-1][1] >= 400
    assert set(log_levels) >= {"audit", "debug"}
    assert safe_log_events > 0
    assert secrecy_ok, "Captured SDK diagnostics contained a protected marker"
