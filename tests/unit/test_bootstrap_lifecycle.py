"""Concurrency, resource ownership, failure budgets and diagnostic safety."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from miso_client import BootstrapError, init_secrets
from miso_client.utils.bootstrap_identity import AzureIdentityProvider
from miso_client.utils.bootstrap_runtime import SecretsRuntime
from miso_client.utils.bootstrap_snapshot import parse_snapshot
from miso_client.utils.bootstrap_transport import BrokerTransport, validate_settings
from tests.unit.test_bootstrap import Identity, azure_env, response_data


@pytest.mark.asyncio
async def test_single_flight_waiter_cancel_and_close_late_response():
    ready = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        ready.set()
        await release.wait()
        return json.dumps(response_data()).encode()

    runtime = SecretsRuntime()
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    transport.fetch = fetch
    runtime.attach_transport(transport)
    first = asyncio.create_task(runtime.refresh())
    await ready.wait()
    second = asyncio.create_task(runtime.refresh())
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        _ = await first
    release.set()
    assert await second is None
    assert calls == 1
    assert runtime.secrets.require("DATABASE_URL") == "secret-sentinel"
    await runtime.close()
    assert transport.client.is_closed


@pytest.mark.asyncio
async def test_close_during_refresh_cannot_repopulate():
    ready = asyncio.Event()

    async def fetch():
        ready.set()
        try:
            await asyncio.Future()
            raise AssertionError("unreachable")
        except asyncio.CancelledError:
            return json.dumps(response_data()).encode()

    runtime = SecretsRuntime()
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    transport.fetch = fetch
    runtime.attach_transport(transport)
    task = asyncio.create_task(runtime.refresh())
    await ready.wait()
    await runtime.close()
    assert await task is None
    with pytest.raises(BootstrapError, match="closed"):
        runtime.secrets.get("DATABASE_URL")


@pytest.mark.asyncio
async def test_refresh_failure_cooldown_prevents_request_storm():
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    fetch = AsyncMock(side_effect=BootstrapError("temporarily-unavailable"))
    transport.fetch = fetch
    runtime = SecretsRuntime()
    runtime.attach_transport(transport)
    runtime.install(parse_snapshot(json.dumps(response_data()).encode(), time.time()))
    for _ in range(4):
        with pytest.raises(BootstrapError):
            await runtime.refresh()
    assert fetch.call_count == 1
    assert runtime.secrets.get("DATABASE_URL") == "secret-sentinel"
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["authorization-denied", "protocol-error"])
async def test_refresh_terminal_failure_revokes_snapshot(code):
    runtime = SecretsRuntime()
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    transport.fetch = AsyncMock(side_effect=BootstrapError(code))
    runtime.attach_transport(transport)
    runtime.install(parse_snapshot(json.dumps(response_data()).encode(), time.time()))
    with pytest.raises(BootstrapError):
        await runtime.refresh()
    with pytest.raises(BootstrapError):
        await runtime.get_token()
    await runtime.close()


@pytest.mark.asyncio
async def test_identity_error_is_sanitized_and_not_retried():
    provider = Identity()
    provider.get_token = AsyncMock(side_effect=ValueError("identity-secret-sentinel"))
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", provider)
    with pytest.raises(BootstrapError) as caught:
        await transport.fetch()
    assert "identity-secret-sentinel" not in str(caught.value)
    assert caught.value.__context__ is None
    assert provider.get_token.call_count == 1
    await transport.close()


@pytest.mark.asyncio
async def test_http_maximum_three_attempts():
    handler = AsyncMock(return_value=httpx.Response(503))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = BrokerTransport(
            "https://miso.test/api/v1/auth/bootstrap", "api://b", Identity(), client
        )
        with patch("miso_client.utils.bootstrap_transport.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(BootstrapError):
                await transport.fetch()
    assert handler.call_count == 3


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://host",
        "https://user:pass@host",
        "https://host/path",
        "https://host?q=1",
        "https://host#x",
        "https://host:bad",
    ],
)
def test_bad_url_rejected_before_identity(url):
    with pytest.raises(BootstrapError):
        validate_settings(url, "api://b")


def test_scope_is_not_accepted_as_audience():
    with pytest.raises(BootstrapError):
        validate_settings("https://host", "api://b/.default")


def test_missing_azure_dependency_has_safe_error():
    with patch(
        "miso_client.utils.bootstrap_identity.importlib.import_module",
        side_effect=ImportError("secret-sentinel"),
    ):
        with pytest.raises(BootstrapError, match="azure-extra-unavailable") as caught:
            AzureIdentityProvider()
    assert caught.value.__context__ is None


def test_python38_azure_guard_before_import():
    with patch("miso_client.utils.bootstrap_identity.sys.version_info", (3, 8)), patch(
        "miso_client.utils.bootstrap_identity.importlib.import_module",
        side_effect=AssertionError("not imported"),
    ):
        with pytest.raises(BootstrapError, match="azure-requires-python"):
            AzureIdentityProvider()


@pytest.mark.asyncio
async def test_failed_init_closes_owned_identity(monkeypatch):
    azure_env(monkeypatch)
    owned = Identity()
    with patch("miso_client.utils.bootstrap.AzureIdentityProvider", return_value=owned):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(404))
        ) as client:
            with pytest.raises(BootstrapError):
                await init_secrets(http_client=client)
    assert owned.closed


@pytest.mark.asyncio
async def test_azure_adapter_get_token_and_close():
    from types import SimpleNamespace

    credential = SimpleNamespace(
        get_token=AsyncMock(
            return_value=SimpleNamespace(token="sentinel", expires_on=int(time.time()) + 600)
        ),
        close=AsyncMock(),
    )
    module = SimpleNamespace(ManagedIdentityCredential=lambda **kw: credential)
    with patch("miso_client.utils.bootstrap_identity.importlib.import_module", return_value=module):
        provider = AzureIdentityProvider("selected-id")
        token = await provider.get_token("api://b/.default")
        assert token.token.get_secret_value() == "sentinel"
        assert "sentinel" not in repr(token)
        await provider.close()
        credential.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_failure_stays_closed_and_is_sanitized():
    runtime = SecretsRuntime({"KEY": "secret-sentinel"})
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    transport.close = AsyncMock(side_effect=ValueError("secret-sentinel"))
    runtime.attach_transport(transport)
    for _ in range(2):
        with pytest.raises(BootstrapError, match="cleanup-failed") as caught:
            await runtime.close()
        assert caught.value.__context__ is None
        assert "secret-sentinel" not in str(caught.value)
    with pytest.raises(BootstrapError, match="closed"):
        runtime.secrets.get("KEY")
    await transport.client.aclose()


@pytest.mark.asyncio
async def test_cleanup_timeout_returns_even_when_cleanup_pending():
    runtime = SecretsRuntime()
    waiting = asyncio.Event()

    async def cleanup():
        waiting.set()
        await asyncio.Future()

    runtime._cleanup = cleanup
    original_wait = asyncio.wait

    async def short_wait(tasks, timeout):
        assert timeout == 5
        await waiting.wait()
        return await original_wait(tasks, timeout=0)

    with patch("miso_client.utils.bootstrap_runtime.asyncio.wait", side_effect=short_wait):
        with pytest.raises(BootstrapError, match="cleanup-failed"):
            await runtime.close()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_background_refresh_uses_elapsed_time_after_wall_clock_rollback():
    runtime = SecretsRuntime()
    wall = time.time()
    monotonic = time.monotonic()
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=wall), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=monotonic
    ), patch("miso_client.utils.bootstrap_runtime.random.uniform", return_value=110):
        runtime.install(parse_snapshot(json.dumps(response_data()).encode(), wall))
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=wall - 3600), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=monotonic + 115
    ):
        assert runtime._refresh_delay() == 0
        runtime._next_attempt = monotonic + 145
        assert runtime._refresh_delay() == pytest.approx(30)
    await runtime.close()


@pytest.mark.asyncio
async def test_background_expiry_notifies_without_consumer_access():
    runtime = SecretsRuntime()
    wall = time.time()
    monotonic = time.monotonic()
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=wall), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=monotonic
    ):
        runtime.install(parse_snapshot(json.dumps(response_data()).encode(), wall))
    reasons = []
    runtime.on_invalidated(reasons.append)
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=wall - 3600), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=monotonic + 901
    ):
        await runtime._run_refresh()
    assert reasons == ["snapshot-expired"]
    await runtime.close()


def test_deeply_nested_broker_json_is_a_safe_protocol_failure():
    with pytest.raises(BootstrapError, match="protocol-error") as error:
        parse_snapshot(b"[" * 2000 + b"]" * 2000, time.time())
    assert error.value.__context__ is None
