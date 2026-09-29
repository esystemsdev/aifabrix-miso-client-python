"""Live controller tests for application-token concurrency and lifecycle.

Uses the existing integration auth preflight and MISO_* environment configuration.
Optional MISO_TOKEN_E2E_CLIENT_ID/SECRET/CONTROLLER_URL isolate a registered test app.
All HTTP requests use real httpx transports; hooks only observe requests or pause
response delivery for deterministic cancellation and invalidation checks.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Callable
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from miso_client import MisoClient
from miso_client.errors import AuthenticationError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.client_token_manager import ClientTokenManager

pytestmark = pytest.mark.integration
CALLERS = 24


class MintObserver:
    """Observe real mint traffic without substituting a transport or response."""

    def __init__(self) -> None:
        self.requests = 0
        self.statuses: list[int] = []
        self.correlations: list[str] = []
        self.clients: list[httpx.AsyncClient] = []
        self.pause_response = False
        self.response_received = asyncio.Event()
        self.release_response = asyncio.Event()

    async def on_request(self, request: httpx.Request) -> None:
        self.requests += 1
        correlation = str(uuid4())
        self.correlations.append(correlation)
        request.headers["x-correlation-id"] = correlation

    async def on_response(self, response: httpx.Response) -> None:
        self.statuses.append(response.status_code)
        self.response_received.set()
        if self.pause_response:
            await self.release_response.wait()


@pytest.fixture
def mint_observer(monkeypatch: pytest.MonkeyPatch) -> MintObserver:
    """Attach event hooks to the existing, real token HTTP client factory."""
    observer = MintObserver()
    original = ClientTokenManager._create_temp_client

    def observed_client(manager: ClientTokenManager, client_id: str) -> httpx.AsyncClient:
        transport = original(manager, client_id)
        transport.event_hooks["request"].append(observer.on_request)
        transport.event_hooks["response"].append(observer.on_response)
        observer.clients.append(transport)
        return transport

    monkeypatch.setattr(ClientTokenManager, "_create_temp_client", observed_client)
    return observer


@pytest.fixture
def live_config() -> MisoClientConfig:
    """Require real registered-app credentials; never skip unavailable live tests."""
    names = {
        "controller_url": ("MISO_TOKEN_E2E_CONTROLLER_URL", "MISO_CONTROLLER_URL"),
        "client_id": ("MISO_TOKEN_E2E_CLIENT_ID", "MISO_CLIENTID"),
        "client_secret": ("MISO_TOKEN_E2E_CLIENT_SECRET", "MISO_CLIENTSECRET"),
    }
    values = {
        key: os.getenv(override) or os.getenv(default, "")
        for key, (override, default) in names.items()
    }
    if not all(values.values()):
        pytest.fail("Live token tests require controller URL and registered test-app credentials.")
    return MisoClientConfig(
        controller_url=values["controller_url"],
        client_id=values["client_id"],
        client_secret=values["client_secret"],
    )


@pytest_asyncio.fixture
async def live_client(
    live_config: MisoClientConfig, mint_observer: MintObserver
) -> AsyncIterator[MisoClient]:
    """Own one SDK client on the test loop, with Redis disabled."""
    client = MisoClient(live_config)
    await client.initialize()
    try:
        yield client
    finally:
        mint_observer.release_response.set()
        await client.disconnect()


async def successful_burst(client: MisoClient) -> str:
    """Obtain a shared token without exposing token/credential values on failure."""
    results = await asyncio.wait_for(
        asyncio.gather(
            *(client.get_environment_token() for _ in range(CALLERS)), return_exceptions=True
        ),
        timeout=45,
    )
    if not all(isinstance(value, str) and value for value in results):
        pytest.fail(
            "The live token mint failed; inspect controller correlation IDs.", pytrace=False
        )
    tokens = [value for value in results if isinstance(value, str)]
    unique_tokens = len(set(tokens))
    assert unique_tokens == 1, "Concurrent callers must receive the same token"
    return tokens[0]


async def validate_at_controller(client: MisoClient, token: str) -> None:
    """Prove the minted token is accepted by a second real controller endpoint."""
    try:
        result = await client.validate_client_token(token)
    except Exception:
        pytest.fail("Controller token validation request failed.", pytrace=False)
    else:
        assert result.data.authenticated, "Controller rejected the minted application token"


def record_traffic(observer: MintObserver, record_property: Callable[[str, object], None]) -> None:
    """Record counts/status/correlation IDs only; never tokens or credentials."""
    record_property("mint_requests", observer.requests)
    record_property("mint_statuses", ",".join(map(str, observer.statuses)))
    record_property("mint_correlations", ",".join(observer.correlations))
    assert all(client.is_closed for client in observer.clients), "Temporary mint clients must close"


@pytest.mark.asyncio
async def test_live_concurrent_success_reuses_controller_validated_token(
    live_client: MisoClient,
    mint_observer: MintObserver,
    record_property: Callable[[str, object], None],
) -> None:
    token = await successful_burst(live_client)
    reused = await live_client.get_environment_token()
    if reused != token:
        pytest.fail("Sequential calls must reuse the minted token", pytrace=False)
    await validate_at_controller(live_client, token)
    assert mint_observer.requests == 1
    assert mint_observer.statuses[0] in (200, 201)
    record_traffic(mint_observer, record_property)


@pytest.mark.asyncio
async def test_live_denied_burst_shares_failure_and_corrected_credentials_retry(
    live_client: MisoClient,
    mint_observer: MintObserver,
    record_property: Callable[[str, object], None],
) -> None:
    correct_secret = live_client.config.client_secret
    live_client.config.client_secret = "deliberately-invalid-e2e-" + uuid4().hex
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                *(live_client.get_environment_token() for _ in range(CALLERS)),
                return_exceptions=True,
            ),
            timeout=45,
        )
    finally:
        live_client.config.client_secret = correct_secret
    assert all(
        isinstance(value, AuthenticationError) and value.status_code == 401 for value in results
    )
    assert mint_observer.requests == 1, "A denied burst must make exactly one real mint request"
    assert mint_observer.statuses == [401]
    token = await successful_burst(live_client)
    await validate_at_controller(live_client, token)
    assert mint_observer.requests == 2, "A later call must be able to retry immediately"
    record_traffic(mint_observer, record_property)


@pytest.mark.asyncio
async def test_live_waiter_cancellation_preserves_other_callers(
    live_client: MisoClient,
    mint_observer: MintObserver,
    record_property: Callable[[str, object], None],
) -> None:
    mint_observer.pause_response = True
    callers = [asyncio.create_task(live_client.get_environment_token()) for _ in range(CALLERS)]
    try:
        await asyncio.wait_for(mint_observer.response_received.wait(), timeout=35)
        callers[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await callers[0]
        mint_observer.release_response.set()
        tokens = await asyncio.wait_for(asyncio.gather(*callers[1:]), timeout=10)
        unique_tokens = len(set(tokens))
        assert unique_tokens == 1
        await validate_at_controller(live_client, tokens[0])
        assert mint_observer.requests == 1
        record_traffic(mint_observer, record_property)
    finally:
        mint_observer.release_response.set()
        for caller in callers:
            caller.cancel()
        await asyncio.gather(*callers, return_exceptions=True)


@pytest.mark.asyncio
async def test_live_clear_rejects_late_controller_response_then_recovers(
    live_client: MisoClient,
    mint_observer: MintObserver,
    record_property: Callable[[str, object], None],
) -> None:
    mint_observer.pause_response = True
    caller = asyncio.create_task(live_client.get_environment_token())
    try:
        await asyncio.wait_for(mint_observer.response_received.wait(), timeout=35)
        assert mint_observer.statuses[0] in (200, 201)
        manager = live_client.http_client.get_internal_client().token_manager
        manager.clear_token()
        mint_observer.release_response.set()
        with pytest.raises(AuthenticationError, match="invalidated"):
            await asyncio.wait_for(caller, timeout=10)
        assert manager.client_token is None
        token = await successful_burst(live_client)
        await validate_at_controller(live_client, token)
        assert mint_observer.requests == 2
        record_traffic(mint_observer, record_property)
    finally:
        caller.cancel()
        await asyncio.gather(caller, return_exceptions=True)


@pytest.mark.asyncio
async def test_live_close_settles_mint_and_closes_transport(
    live_client: MisoClient,
    mint_observer: MintObserver,
    record_property: Callable[[str, object], None],
) -> None:
    mint_observer.pause_response = True
    caller = asyncio.create_task(live_client.get_environment_token())
    try:
        await asyncio.wait_for(mint_observer.response_received.wait(), timeout=35)
        assert mint_observer.statuses[0] in (200, 201)
        await asyncio.wait_for(live_client.disconnect(), timeout=10)
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert live_client.http_client.get_internal_client().token_manager.client_token is None
        assert mint_observer.requests == 1
        record_traffic(mint_observer, record_property)
    finally:
        mint_observer.release_response.set()
        caller.cancel()
        await asyncio.gather(caller, return_exceptions=True)
