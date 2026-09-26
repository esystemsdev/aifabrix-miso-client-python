"""Client-credential exchange, snapshot token chaining and confidential failures."""

import asyncio
import json
import ssl
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from miso_client import BootstrapError, init_secrets
from miso_client.utils.bootstrap_credentials import parse_minted_token, validate_settings
from miso_client.utils.bootstrap_runtime import SecretsRuntime
from miso_client.utils.bootstrap_snapshot import MAX_BODY, parse_snapshot
from miso_client.utils.bootstrap_transport import BrokerTransport
from tests.unit.test_bootstrap import credential_env, mint_data, mint_or_snapshot, response_data


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["", "/", "/miso", "/miso/", "/platform/miso"])
async def test_mint_then_snapshot_preserves_prefix_and_ignores_client_defaults(prefix):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host == "miso.test"
        assert request.url.query == b""
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        if request.url.path.endswith("/token"):
            assert request.headers["x-client-id"] == "client"
            assert request.headers["x-client-secret"] == "credential-sentinel"
            assert "x-client-token" not in request.headers
            assert request.content == b""
        else:
            assert "x-client-id" not in request.headers
            assert "x-client-secret" not in request.headers
            assert request.headers["x-client-token"] == "mint-sentinel"
            assert json.loads(request.content) == {"protocolVersion": 1}
        return mint_or_snapshot(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        trust_env=False,
        base_url="https://attacker.test",
        auth=("user", "password"),
        params={"leak": "value"},
        cookies={"secret": "cookie-sentinel"},
        headers={
            "Authorization": "Bearer default",
            "x-client-secret": "default-secret",
            "x-client-token": "default-token",
        },
    ) as client:
        broker = BrokerTransport(
            validate_settings("https://miso.test" + prefix), "client", "credential-sentinel", client
        )
        await broker.fetch()
        await broker.close()
        assert not client.is_closed
    assert [r.url.path for r in seen] == [
        prefix.rstrip("/") + "/api/v1/auth/" + suffix for suffix in ("token", "bootstrap")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["token", "bootstrap"])
@pytest.mark.parametrize("status", [401, 403, 302, 404, 422, 500])
async def test_terminal_status_at_each_step_never_retries_or_falls_back(stage, status):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path.endswith("/" + stage):
            return httpx.Response(
                status, text="secret-sentinel", headers={"Location": "https://attacker.test"}
            )
        return mint_or_snapshot(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        with pytest.raises(BootstrapError) as error:
            await broker.fetch()
        assert error.value.code == (
            "authorization-denied" if status in (401, 403) else "protocol-error"
        )
        assert error.value.__context__ is None
        assert "secret-sentinel" not in repr(error.value)
    assert len(seen) == (1 if stage == "token" else 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["token", "bootstrap"])
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_transient_status_at_each_step_retries(stage, status):
    failures = 0

    def handler(request):
        nonlocal failures
        if request.url.path.endswith("/" + stage) and failures < 2:
            failures += 1
            return httpx.Response(status, headers={"Retry-After": "0"})
        return mint_or_snapshot(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        assert parse_snapshot(await broker.fetch(), time.time()).clientId == "client"
    assert failures == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(token=""),
        lambda d: d.update(token=" "),
        lambda d: d.update(token="x" * 65537),
        lambda d: d.update(token=123),
        lambda d: d.pop("token"),
        lambda d: d.update(expiresIn=True),
        lambda d: d.update(expiresIn=float("nan")),
        lambda d: d.update(expiresIn=float("inf")),
        lambda d: d.update(expiresIn=0),
        lambda d: d.update(expiresIn=-1),
        lambda d: d.update(expiresAt="bad"),
        lambda d: d.update(expiresAt="2000-01-01T00:00:00Z"),
        lambda d: d.pop("expiresAt"),
    ],
)
def test_invalid_mint_values_are_safe_protocol_failures(mutate):
    body = mint_data()
    mutate(body["data"])
    with pytest.raises(BootstrapError, match="protocol-error") as error:
        parse_minted_token(json.dumps(body).encode())
    assert error.value.__context__ is None
    assert "mint-sentinel" not in repr(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        b"[]",
        b"null",
        b"{",
        b'{"data":{},"data":{}}',
        b'{"success":false,"data":{}}',
        b"x" * (MAX_BODY + 1),
    ],
)
async def test_bad_mint_response_prevents_snapshot_access(body):
    handler = AsyncMock(return_value=httpx.Response(201, content=body))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        with pytest.raises(BootstrapError, match="protocol-error"):
            await broker.fetch()
    assert handler.call_count == 1


@pytest.mark.asyncio
async def test_rotation_uses_successive_snapshot_tokens_and_never_rereads_credentials(monkeypatch):
    credential_env(monkeypatch)
    tokens = []
    mint_calls = 0

    def handler(request):
        nonlocal mint_calls
        if request.url.path.endswith("/token"):
            mint_calls += 1
            return httpx.Response(201, json=mint_data())
        tokens.append(request.headers["x-client-token"])
        data = response_data()
        data["data"]["clientToken"] = f"snapshot-{len(tokens)}"
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        runtime = await init_secrets(http_client=client)
        monkeypatch.setenv("MISO_CLIENTSECRET", "rotated-secret")
        monkeypatch.setenv("MISO_CONTROLLER_URL", "https://attacker.test")
        await runtime.refresh()
        await runtime.refresh()
        assert await runtime.get_token() == "snapshot-3"
        assert runtime._transport is not None
        assert runtime._transport._credentials is None
        assert "snapshot-3" not in repr(vars(runtime._transport))
        await runtime.close()
        assert runtime._transport._token is None
        with pytest.raises(BootstrapError, match="closed"):
            await runtime.refresh()
    assert mint_calls == 1
    assert tokens == ["mint-sentinel", "snapshot-1", "snapshot-2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["context", "clientId", "extra", "denied"])
async def test_invalid_refresh_clears_tokens_without_remint_or_revival(failure):
    calls = []
    data = response_data()

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/token"):
            return httpx.Response(201, json=mint_data())
        if len(calls) > 2:
            if failure == "denied":
                return httpx.Response(403)
            if failure == "context":
                data["data"]["context"]["applicationId"] = "other"
            else:
                data["data"][failure] = "other"
            data["data"]["clientToken"] = "untrusted-token"
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        runtime = SecretsRuntime()
        runtime.attach_transport(broker)
        await runtime.refresh()
        with pytest.raises(BootstrapError):
            await runtime.refresh()
        assert broker._token is None and broker._credentials is None
        with pytest.raises(BootstrapError):
            await runtime.refresh()
        await runtime.close()
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_snapshot_token_recovers_bootstrap_after_api_deadline_but_not_secret_deadline():
    handler = AsyncMock(side_effect=mint_or_snapshot)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        runtime = SecretsRuntime()
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        runtime.attach_transport(broker)
        await runtime.refresh()
        assert runtime._clock is not None
        with patch.object(runtime._clock, "now", return_value=time.time() + 301):
            assert await runtime.get_token() == "application-sentinel"
        assert handler.call_count == 3
        assert handler.call_args.args[0].headers["x-client-token"] == "application-sentinel"
        assert runtime._clock is not None
        with patch.object(runtime._clock, "now", return_value=time.time() + 901):
            with pytest.raises(BootstrapError, match="snapshot-expired"):
                await runtime.refresh()
        assert handler.call_count == 3
        assert broker._token is None
        await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [httpx.ConnectError, httpx.ReadTimeout])
async def test_network_failure_has_three_bounded_attempts_and_safe_error(exception, caplog):
    handler = AsyncMock(side_effect=exception("credential-sentinel"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        with patch("miso_client.utils.bootstrap_transport.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(BootstrapError, match="temporarily-unavailable") as error:
                await broker.fetch()
        assert error.value.__context__ is None
        assert "credential-sentinel" not in caplog.text
    assert handler.call_count == 3


@pytest.mark.asyncio
async def test_tls_failure_is_terminal_without_raw_diagnostics():
    error = httpx.ConnectError("credential-sentinel")
    error.__cause__ = ssl.SSLError("credential-sentinel")
    handler = AsyncMock(side_effect=error)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        with pytest.raises(BootstrapError, match="transport-error") as caught:
            await broker.fetch()
        assert caught.value.__context__ is None
    assert handler.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("hooks", [False, True])
async def test_unsafe_injected_client_rejected_before_network(hooks):
    handler = AsyncMock()
    hook = AsyncMock()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        trust_env=not hooks,
        event_hooks={"request": [hook]} if hooks else {},
    ) as client:
        with pytest.raises(BootstrapError, match="invalid-bootstrap-http-client"):
            BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
    handler.assert_not_called()
    hook.assert_not_called()


@pytest.mark.asyncio
async def test_shared_total_budget_and_per_attempt_timeout():
    waits = []
    original = asyncio.wait_for

    async def bounded(work, timeout):
        waits.append(timeout)
        return await original(work, timeout)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(mint_or_snapshot), trust_env=False
    ) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        with patch("miso_client.utils.bootstrap_transport.asyncio.wait_for", side_effect=bounded):
            await broker.fetch()
    assert waits == [30, 5, 5]


@pytest.mark.asyncio
async def test_initialization_cancellation_cleans_owned_client(monkeypatch):
    credential_env(monkeypatch)
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Future()
        raise AssertionError("unreachable")

    owned = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    with patch("miso_client.utils.bootstrap_transport.httpx.AsyncClient", return_value=owned):
        task = asyncio.create_task(init_secrets())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert owned.is_closed


@pytest.mark.asyncio
async def test_invalidation_during_mint_does_not_restore_retained_token():
    runtime = SecretsRuntime()
    broker = None

    def handler(request):
        runtime.invalidate("authorization-denied")
        return httpx.Response(201, json=mint_data())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        runtime.attach_transport(broker)
        with pytest.raises(BootstrapError):
            await runtime.refresh()
        assert broker._token is None
        assert broker._credentials is None
        await runtime.close()


@pytest.mark.asyncio
async def test_expiration_during_retry_prevents_another_snapshot_request():
    runtime = SecretsRuntime()
    failed = False
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if failed:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return mint_or_snapshot(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        runtime.attach_transport(broker)
        await runtime.refresh()
        failed = True
        assert runtime._clock is not None
        # Active at entry and first attempt, expired before the next attempt.
        with patch.object(
            runtime._clock, "now", side_effect=[time.time(), time.time(), time.time() + 901]
        ):
            with pytest.raises(BootstrapError, match="snapshot-expired"):
                await runtime.refresh()
        assert calls == 3
        assert broker._token is None
        with pytest.raises(BootstrapError, match="snapshot-expired"):
            runtime.secrets.get("DATABASE_URL")
        await runtime.close()


@pytest.mark.parametrize(
    "client_id,secret",
    [("", "s"), ("c", ""), ("c", " "), ("c", "s\r\nInjected: value"), ("c", "é")],
)
def test_missing_or_unsafe_credentials_fail_before_client_creation(client_id, secret):
    with patch("httpx.AsyncClient", side_effect=AssertionError("no client")):
        with pytest.raises(BootstrapError, match="invalid-bootstrap-settings"):
            BrokerTransport(validate_settings("https://miso.test"), client_id, secret)


@pytest.mark.asyncio
async def test_long_retry_after_aborts_without_wait_or_second_attempt():
    handler = AsyncMock(return_value=httpx.Response(503, headers={"Retry-After": "11"}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        with patch("miso_client.utils.bootstrap_transport.asyncio.sleep", new=AsyncMock()) as sleep:
            with pytest.raises(BootstrapError, match="temporarily-unavailable"):
                await broker.fetch()
            sleep.assert_not_called()
    assert handler.call_count == 1


@pytest.mark.asyncio
async def test_initial_exchange_total_timeout_cancels_snapshot_and_cleans_state(monkeypatch):
    credential_env(monkeypatch)
    snapshot_started = asyncio.Event()
    snapshot_cancelled = asyncio.Event()
    original = asyncio.wait_for

    async def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(201, json=mint_data())
        snapshot_started.set()
        try:
            await asyncio.Future()
        finally:
            snapshot_cancelled.set()
        raise AssertionError("unreachable")

    async def exhaust_budget(work, timeout):
        if timeout != 30:
            return await original(work, timeout)
        running = asyncio.create_task(work)
        await snapshot_started.wait()
        # Exhaust the total budget after minting, while the snapshot is pending.
        return await original(running, 0)

    owned = httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)
    with patch(
        "miso_client.utils.bootstrap_transport.httpx.AsyncClient", return_value=owned
    ), patch("miso_client.utils.bootstrap_transport.asyncio.wait_for", side_effect=exhaust_budget):
        with pytest.raises(BootstrapError, match="temporarily-unavailable"):
            await init_secrets()
    assert snapshot_cancelled.is_set()
    assert owned.is_closed


@pytest.mark.asyncio
async def test_snapshot_response_after_previous_deadline_cannot_restore_runtime():
    runtime = SecretsRuntime()
    handler = AsyncMock(side_effect=mint_or_snapshot)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(validate_settings("https://miso.test"), "client", "secret", client)
        runtime.attach_transport(broker)
        await runtime.refresh()
        assert runtime._clock is not None
        with patch.object(
            runtime._clock, "now", side_effect=[time.time(), time.time(), time.time() + 901]
        ):
            with pytest.raises(BootstrapError, match="snapshot-expired"):
                await runtime.refresh()
        assert broker._token is None
        with pytest.raises(BootstrapError):
            await runtime.get_token()
        await runtime.close()
