"""Normal API errors must distinguish user/RBAC failures from runtime revocation."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from miso_client import BootstrapError, MisoClientConfig, MisoClientError
from miso_client.utils.bootstrap_runtime import SecretsRuntime
from miso_client.utils.bootstrap_snapshot import parse_snapshot
from miso_client.utils.bootstrap_transport import BrokerTransport
from miso_client.utils.internal_http_client import InternalHttpClient
from tests.unit.test_bootstrap import Identity, response_data


def runtime_with_snapshot():
    runtime = SecretsRuntime()
    runtime.install(parse_snapshot(json.dumps(response_data()).encode(), time.time()))
    return runtime


def client_for(runtime, handler):
    config = MisoClientConfig(
        controller_url="https://miso.test",
        client_id="client",
        application_token_provider=runtime,
        runtime_guard=runtime.ensure_active,
    )
    client = InternalHttpClient(config)
    client.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url=config.controller_url
    )
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body",
    [
        (403, {"code": "permission_denied"}),
        (401, {"code": "user_token_expired"}),
        (403, {}),
        (401, {}),
        (503, {"code": "bootstrap_registry_unavailable"}),
        (403, {"code": "bootstrap_token_expired"}),
        (401, {"code": {"bad": "value"}}),
    ],
)
async def test_unrelated_errors_do_not_revoke_or_refresh(status, body):
    runtime = runtime_with_snapshot()
    client = client_for(runtime, lambda r: httpx.Response(status, json=body))
    with patch.object(runtime, "refresh", new=AsyncMock()) as refresh:
        with pytest.raises(MisoClientError):
            await client.get("/ordinary")
        assert runtime.secrets.get("DATABASE_URL") == "secret-sentinel"
        assert await runtime.get_token() == "application-sentinel"
        refresh.assert_not_awaited()
    await runtime.close()
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (403, "bootstrap_identity_disabled"),
        (403, "bootstrap_binding_mismatch"),
        (401, "bootstrap_token_invalid"),
    ],
)
async def test_typed_identity_failure_invalidates_before_next_request(status, code):
    runtime = runtime_with_snapshot()
    handler = AsyncMock(return_value=httpx.Response(status, json={"code": code}))
    client = client_for(runtime, handler)
    with pytest.raises(MisoClientError):
        await client.get("/ordinary")
    with pytest.raises(BootstrapError, match="authorization-denied"):
        runtime.secrets.get("DATABASE_URL")
    with pytest.raises(BootstrapError):
        await client.get("/ordinary")
    assert handler.call_count == 1
    await runtime.close()
    await client.close()


@pytest.mark.asyncio
async def test_expired_token_refreshes_concurrent_responses_without_replaying_mutations():
    runtime = runtime_with_snapshot()
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    started = asyncio.Event()
    release = asyncio.Event()

    async def fetch():
        started.set()
        await release.wait()
        data = response_data()
        data["data"]["clientToken"] = "replacement-sentinel"
        return json.dumps(data).encode()

    transport.fetch = AsyncMock(side_effect=fetch)
    runtime.attach_transport(transport)
    both_sent = asyncio.Event()
    sent = 0

    async def deny(request):
        nonlocal sent
        sent += 1
        if sent == 2:
            both_sent.set()
        await both_sent.wait()
        return httpx.Response(401, json={"code": "bootstrap_token_expired"})

    handler = AsyncMock(side_effect=deny)
    client = client_for(runtime, handler)
    calls = [asyncio.create_task(client.post("/mutation", {"value": 1})) for _ in range(2)]
    await started.wait()
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*calls, return_exceptions=True)
    assert all(isinstance(result, MisoClientError) for result in results)
    assert handler.call_count == 2  # No automatic replay of either POST.
    assert transport.fetch.call_count == 1
    assert await runtime.get_token() == "replacement-sentinel"
    await runtime.handle_auth_error("bootstrap_token_expired", "application-sentinel")
    assert transport.fetch.call_count == 1  # Late failure for the old token is stale.
    await runtime.close()
    await client.close()


@pytest.mark.asyncio
async def test_failed_expiry_refresh_cannot_reuse_rejected_token():
    runtime = runtime_with_snapshot()
    transport = BrokerTransport("https://miso.test/api/v1/auth/bootstrap", "api://b", Identity())
    transport.fetch = AsyncMock(side_effect=BootstrapError("temporarily-unavailable"))
    runtime.attach_transport(transport)
    client = client_for(
        runtime, lambda r: httpx.Response(401, json={"code": "bootstrap_token_expired"})
    )
    with pytest.raises(MisoClientError):
        await client.post("/mutation")
    with pytest.raises(BootstrapError):
        await runtime.get_token()
    assert runtime.secrets.require("DATABASE_URL") == "secret-sentinel"
    assert transport.fetch.call_count == 1
    await runtime.close()
    await client.close()
