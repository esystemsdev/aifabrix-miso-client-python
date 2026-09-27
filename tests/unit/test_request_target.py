"""The client token belongs to the controller origin and to nothing else.

Before 5.0 the SDK attached ``x-client-token`` to every request, including
provider calls; 5.0 refused every non-controller target instead. Both were
wrong for workloads that call providers through the same client. Requests are
now routed by origin: controller targets keep token, pin and bootstrap
handling; external targets travel credential-free.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from miso_client.models.config import MisoClientConfig
from miso_client.utils.internal_http_client import InternalHttpClient
from miso_client.utils.request_target import RequestTarget, origin_of
from tests.unit.test_bootstrap_auth import client_for, runtime_with_snapshot

CONTROLLER = "https://miso.test"


def _config(**extra):
    return MisoClientConfig(
        controller_url=CONTROLLER, client_id="client", client_secret="secret", **extra
    )


class _Recorder:
    def __init__(self, response: httpx.Response):
        self.requests = []
        self._response = response

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._response


def _attach_external(client: InternalHttpClient, handler) -> None:
    client._external = httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _legacy_client(controller_handler, external_handler, **extra) -> InternalHttpClient:
    config = _config(**extra)
    client = InternalHttpClient(config)
    client.client = httpx.AsyncClient(
        transport=httpx.MockTransport(controller_handler), base_url=CONTROLLER
    )
    _attach_external(client, external_handler)
    return client


class TestOriginRule:
    def test_origin_of_normalises_scheme_host_and_port(self):
        assert origin_of("HTTPS://Miso.Test:443/api") == ("https", "miso.test", 443)
        assert origin_of("http://miso-controller:3000/miso") == ("http", "miso-controller", 3000)
        # [EDGE] relative paths, empty and malformed values are not origins
        assert origin_of("/api/v1/health") is None
        assert origin_of("") is None
        assert origin_of(None) is None

    def test_controller_targets(self):
        target = RequestTarget(_config(controllerPrivateUrl="http://miso-controller:3000/miso"))
        assert target.is_controller("/api/v1/health")
        assert target.is_controller("https://miso.test/api/v1/health")
        assert target.is_controller("https://MISO.test:443/api")
        assert target.is_controller("http://miso-controller:3000/miso/api/v1/auth/token")

    def test_external_targets(self):
        target = RequestTarget(_config())
        assert not target.is_controller("https://api.openai.com/v1/chat/completions")
        # [EDGE] other scheme or other port on the controller host is another origin
        assert not target.is_controller("http://miso.test/api")
        assert not target.is_controller("https://miso.test:8443/api")
        # [EDGE] protocol-relative URLs borrow the scheme; never trusted
        assert not target.is_controller("//miso.test/api")

    def test_strip_sdk_credentials_only(self):
        kwargs = {
            "headers": {
                "X-Client-Token": "t",
                "x-client-id": "i",
                "x-client-secret": "s",
                "Authorization": "Bearer provider-key",
            }
        }
        RequestTarget.strip_sdk_credentials(kwargs)
        assert kwargs["headers"] == {"Authorization": "Bearer provider-key"}
        RequestTarget.strip_sdk_credentials({})  # [EDGE] no headers at all


@pytest.mark.asyncio
class TestLegacyClientRouting:
    async def test_controller_request_carries_client_token(self):
        controller = _Recorder(httpx.Response(200, json={"ok": True}))
        external = _Recorder(httpx.Response(200, json={}))
        client = _legacy_client(controller, external)
        with patch.object(client.token_manager, "get_client_token", AsyncMock(return_value="tok")):
            result = await client.get("/api/v1/health")
        assert result == {"ok": True}
        assert controller.requests[0].headers["x-client-token"] == "tok"
        assert external.requests == []
        await client.close()

    @pytest.mark.parametrize("method", ["get", "get_raw", "post", "put", "patch", "delete"])
    async def test_external_request_carries_no_sdk_credential(self, method):
        controller = _Recorder(httpx.Response(200, json={}))
        external = _Recorder(httpx.Response(200, json={"id": "1"}))
        client = _legacy_client(controller, external)
        client.client.headers["x-client-token"] = "cached-token"  # earlier controller call
        token = AsyncMock(return_value="tok")
        with patch.object(client.token_manager, "get_client_token", token):
            response = await getattr(client, method)(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": "Bearer provider-key", "x-client-token": "leak"},
            )
        token.assert_not_called()
        assert controller.requests == []
        sent = external.requests[0]
        assert sent.url.host == "api.openai.com"
        assert "x-client-token" not in sent.headers
        assert sent.headers["Authorization"] == "Bearer provider-key"
        assert response is not None
        await client.close()

    async def test_external_error_is_not_masked_and_does_not_clear_token(self):
        controller = _Recorder(httpx.Response(200, json={}))
        external = _Recorder(httpx.Response(401, text="Incorrect API key provided"))
        client = _legacy_client(controller, external)
        with patch.object(client.token_manager, "clear_token") as clear:
            with pytest.raises(Exception) as raised:
                await client.post("https://api.openai.com/v1/chat/completions", {"model": "m"})
        # [EDGE] a provider 401 is the provider's verdict, not a client-token problem
        clear.assert_not_called()
        assert getattr(raised.value, "status_code", None) == 401
        assert "Incorrect API key" in str(raised.value)
        await client.close()

    async def test_protocol_relative_url_never_reaches_the_controller_transport(self):
        controller = _Recorder(httpx.Response(200, json={}))
        external = _Recorder(httpx.Response(200, json={}))
        client = _legacy_client(controller, external)
        with patch.object(client.token_manager, "get_client_token", AsyncMock(return_value="tok")):
            with pytest.raises(Exception):
                await client.get("//attacker.test/")
        assert controller.requests == []
        await client.close()

    async def test_close_closes_both_transports(self):
        client = _legacy_client(_Recorder(httpx.Response(200)), _Recorder(httpx.Response(200)))
        await client.close()
        assert client.client is None and client._external is None


@pytest.mark.asyncio
class TestManagedClientRouting:
    async def test_managed_external_request_has_no_token_no_pin_no_invalidation(self):
        runtime = runtime_with_snapshot()
        controller = _Recorder(httpx.Response(200, json={}))
        client = client_for(runtime, controller)
        external = _Recorder(
            httpx.Response(401, json={"code": "bootstrap_token_invalid"}, text=None)
        )
        _attach_external(client, external)
        with patch.object(runtime, "get_token", new_callable=AsyncMock) as token:
            with patch.object(runtime, "handle_auth_error", new_callable=AsyncMock) as revoke:
                with pytest.raises(Exception) as raised:
                    await client.get("https://api.hubapi.com/crm/v3/objects/deals")
        token.assert_not_called()
        # [EDGE] a provider replying with a bootstrap-looking body cannot revoke our runtime
        revoke.assert_not_called()
        assert controller.requests == []
        assert "x-client-token" not in external.requests[0].headers
        assert "follow_redirects" not in external.requests[0].extensions
        assert getattr(raised.value, "status_code", None) == 401
        assert str(raised.value) != "Managed runtime request failed"
        await runtime.close()
        await client.close()

    async def test_managed_controller_request_still_pinned_and_tokened(self):
        runtime = runtime_with_snapshot()
        controller = _Recorder(httpx.Response(200, json={"ok": True}))
        client = client_for(runtime, controller)
        _attach_external(client, _Recorder(httpx.Response(500)))
        with patch.object(runtime, "get_token", AsyncMock(return_value="managed")):
            result = await client.get("/api/v1/health", follow_redirects=True)
        assert result == {"ok": True}
        assert controller.requests[0].headers["x-client-token"] == "managed"
        await runtime.close()
        await client.close()
