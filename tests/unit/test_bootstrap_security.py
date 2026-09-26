"""Adversarial credential-boundary and untrusted broker response checks."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from miso_client import BootstrapError
from miso_client.utils.bootstrap_transport import BrokerTransport
from tests.unit.test_bootstrap_auth import client_for, runtime_with_snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "get_raw", "post", "put", "patch", "delete"])
@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.test/",
        "http://miso.test/",
        "//attacker.test/",
        "https://user:password@miso.test/",
        "https://miso.test:8443/",
    ],
)
async def test_application_token_cannot_leave_pinned_origin(method, url):
    runtime = runtime_with_snapshot()
    handler = AsyncMock(return_value=httpx.Response(200, json={}))
    client = client_for(runtime, handler)
    with patch.object(runtime, "get_token", new_callable=AsyncMock) as token:
        with pytest.raises(BootstrapError, match="untrusted-request-target"):
            await getattr(client, method)(url)
        token.assert_not_called()
    handler.assert_not_called()
    await runtime.close()
    await client.close()


@pytest.mark.asyncio
async def test_redirect_opt_in_cannot_forward_application_token():
    runtime = runtime_with_snapshot()
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(307, headers={"Location": "https://attacker.test/"})

    client = client_for(runtime, handler)
    with pytest.raises(Exception, match="Managed runtime request failed"):
        await client.get("/redirect", follow_redirects=True)
    assert len(seen) == 1
    assert seen[0].url.host == "miso.test"
    await runtime.close()
    await client.close()


@pytest.mark.asyncio
async def test_mutating_client_base_url_cannot_change_trusted_origin():
    runtime = runtime_with_snapshot()
    handler = AsyncMock()
    client = client_for(runtime, handler)
    assert client.client is not None
    client.client.base_url = "https://attacker.test"
    with pytest.raises(BootstrapError, match="untrusted-request-target"):
        await client.get("/data")
    handler.assert_not_called()
    await runtime.close()
    await client.close()


@pytest.mark.asyncio
async def test_broker_rejects_compressed_body_before_iteration():
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail("Compressed data must not reach the decompressor")
            yield b""

    def handler(request):
        assert request.headers["Accept-Encoding"] == "identity"
        return httpx.Response(201, headers={"Content-Encoding": "gzip"}, stream=Body())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as client:
        broker = BrokerTransport(
            "https://miso.test/api/v1/auth/bootstrap", "client", "credential-sentinel", client
        )
        with pytest.raises(BootstrapError, match="protocol-error"):
            await broker.fetch()


@pytest.mark.asyncio
async def test_same_origin_absolute_request_is_allowed():
    runtime = runtime_with_snapshot()
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = client_for(runtime, handler)
    assert await client.get("https://miso.test:443/api/data") == {"ok": True}
    assert seen[0].headers["x-client-token"] == "application-sentinel"
    await runtime.close()
    await client.close()


def test_unknown_success_envelope_members_are_rejected():
    import json
    import time

    from miso_client.utils.bootstrap_snapshot import parse_snapshot
    from tests.unit.test_bootstrap import response_data

    data = response_data()
    data["unexpected"] = "secret-sentinel"
    with pytest.raises(BootstrapError, match="protocol-error") as error:
        parse_snapshot(json.dumps(data).encode(), time.time())
    assert error.value.__context__ is None
