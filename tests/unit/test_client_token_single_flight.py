"""Public token mint concurrency, cancellation, retry and cleanup regressions."""

import asyncio
import gc
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
import pytest_asyncio

from miso_client import MisoClient
from miso_client.errors import AuthenticationError, ConnectionError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.client_token_manager import ClientTokenManager


class MintTransport:
    """Hold real httpx requests at a deterministic barrier."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.requests: list[httpx.Request] = []
        self.clients: list[httpx.AsyncClient] = []
        self.status = 401
        self.network_failure = False

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.started.set()
        await self.release.wait()
        if self.network_failure:
            raise httpx.ConnectError("synthetic connection failure", request=request)
        return httpx.Response(
            self.status,
            headers={"x-correlation-id": "mint-attempt"},
            json={
                "success": True,
                "token": "test-token",
                "expiresIn": 900,
                "expiresAt": "2030-01-01T00:00:00Z",
            },
        )


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> MintTransport:
    stub = MintTransport()
    original = httpx.AsyncClient

    def create_client(**kwargs: Any) -> httpx.AsyncClient:
        client = original(transport=httpx.MockTransport(stub.handle), **kwargs)
        stub.clients.append(client)
        return client

    monkeypatch.setattr(httpx, "AsyncClient", create_client)
    return stub


@pytest_asyncio.fixture
async def client(transport: MintTransport) -> AsyncIterator[MisoClient]:
    sdk = MisoClient(
        MisoClientConfig(
            controller_url="https://controller.test",
            client_id="test-client",
            client_secret="test-secret",
        )
    )
    await sdk.initialize()
    try:
        yield sdk
    finally:
        await sdk.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("network_failure", [False, True])
async def test_concurrent_failure_is_shared_and_next_call_can_retry(
    client: MisoClient, transport: MintTransport, network_failure: bool
) -> None:
    transport.network_failure = network_failure
    callers = [asyncio.create_task(client.get_environment_token()) for _ in range(24)]
    await transport.started.wait()
    transport.release.set()
    results = await asyncio.gather(*callers, return_exceptions=True)
    error_type = ConnectionError if network_failure else AuthenticationError
    assert all(isinstance(result, error_type) for result in results)
    assert len(transport.requests) == 1
    if not network_failure:
        assert all(isinstance(e, AuthenticationError) and e.status_code == 401 for e in results)
        assert all("mint-attempt" in str(e) for e in results)
    transport.status, transport.network_failure = 201, False
    assert await client.get_environment_token() == "test-token"
    assert await client.get_environment_token() == "test-token"
    assert len(transport.requests) == 2
    assert all(connection.is_closed for connection in transport.clients)


@pytest.mark.asyncio
async def test_concurrent_success_is_shared_and_expiry_refreshes(
    client: MisoClient, transport: MintTransport
) -> None:
    transport.status = 201
    callers = [asyncio.create_task(client.get_environment_token()) for _ in range(24)]
    await transport.started.wait()
    transport.release.set()
    assert await asyncio.gather(*callers) == ["test-token"] * 24
    assert len(transport.requests) == 1
    manager = client.http_client.get_internal_client().token_manager
    manager.token_expires_at = datetime.now() - timedelta(seconds=1)
    assert await client.get_environment_token() == "test-token"
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_cancelling_one_waiter_preserves_other_waiters(
    client: MisoClient, transport: MintTransport
) -> None:
    transport.status = 201
    first = asyncio.create_task(client.get_environment_token())
    second = asyncio.create_task(client.get_environment_token())
    await transport.started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    transport.release.set()
    assert await second == "test-token"
    assert len(transport.requests) == 1


@pytest.mark.asyncio
async def test_abandoned_failure_is_consumed(client: MisoClient, transport: MintTransport) -> None:
    loop = asyncio.get_running_loop()
    errors: list[dict[str, Any]] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(context))
    try:
        caller = asyncio.create_task(client.get_environment_token())
        await transport.started.wait()
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        transport.release.set()
        # Let the HTTP response, completion callback and shield cleanup settle.
        for _ in range(4):
            await asyncio.sleep(0)
        gc.collect()
        assert not errors
        assert all(connection.is_closed for connection in transport.clients)
        transport.status = 201
        assert await client.get_environment_token() == "test-token"
        assert len(transport.requests) == 2
    finally:
        loop.set_exception_handler(previous)


@pytest.mark.asyncio
async def test_clear_rejects_late_result_and_allows_retry(
    client: MisoClient, transport: MintTransport
) -> None:
    transport.status = 201
    caller = asyncio.create_task(client.get_environment_token())
    await transport.started.wait()
    manager = client.http_client.get_internal_client().token_manager
    manager.clear_token()
    transport.release.set()
    with pytest.raises(AuthenticationError, match="invalidated"):
        await caller
    assert manager.client_token is None
    assert manager.token_expires_at is None
    assert await client.get_environment_token() == "test-token"
    assert len(transport.requests) == 2


@pytest.mark.asyncio
async def test_close_cancels_mint_and_closes_temporary_transport(
    client: MisoClient, transport: MintTransport
) -> None:
    caller = asyncio.create_task(client.get_environment_token())
    await transport.started.wait()
    await client.disconnect()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert all(connection.is_closed for connection in transport.clients)
    assert client.http_client.get_internal_client().token_manager.client_token is None


@pytest.mark.asyncio
async def test_clear_before_mint_starts_prevents_request(
    client: MisoClient, transport: MintTransport
) -> None:
    caller = asyncio.create_task(client.get_environment_token())
    # The caller queues its mint behind this coroutine's next turn.
    await asyncio.sleep(0)
    client.http_client.get_internal_client().token_manager.clear_token()
    with pytest.raises(AuthenticationError, match="invalidated"):
        await caller
    assert not transport.requests


@pytest.mark.asyncio
async def test_separate_clients_do_not_share_failed_attempts(
    client: MisoClient, transport: MintTransport
) -> None:
    second = ClientTokenManager(
        MisoClientConfig(
            controller_url="https://controller.test",
            client_id="other",
            client_secret="other-secret",
        )
    )
    transport.release.set()
    results = await asyncio.gather(
        client.get_environment_token(), second.get_client_token(), return_exceptions=True
    )
    assert all(isinstance(result, AuthenticationError) for result in results)
    assert len(transport.requests) == 2
    assert {r.headers["x-client-id"] for r in transport.requests} == {"test-client", "other"}
    await second.close()


@pytest.mark.asyncio
async def test_lock_wait_rechecks_current_expiration(
    client: MisoClient, transport: MintTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    manager = client.http_client.get_internal_client().token_manager
    start = datetime(2026, 9, 29)
    clock = Mock(wraps=datetime)
    clock.now.return_value = start
    monkeypatch.setattr("miso_client.utils.client_token_manager.datetime", clock)
    transport.status = 201
    transport.release.set()
    await manager.token_refresh_lock.acquire()
    caller = asyncio.create_task(client.get_environment_token())
    await asyncio.sleep(0)
    manager.client_token = "intervening-token"
    manager.token_expires_at = start + timedelta(seconds=10)
    clock.now.return_value = start + timedelta(seconds=20)
    manager.token_refresh_lock.release()
    assert await caller == "test-token"
    assert len(transport.requests) == 1
