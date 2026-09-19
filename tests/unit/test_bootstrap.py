"""Bootstrap compatibility, isolated transport and actual SDK request tests."""

import builtins
import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from miso_client import BootstrapError, IdentityToken, init_secrets
from miso_client.utils.bootstrap_snapshot import parse_snapshot
from miso_client.utils.bootstrap_transport import BrokerTransport, retry_delay


class Identity:
    def __init__(self):
        self.calls = []
        self.closed = False

    async def get_token(self, scope):
        self.calls.append(scope)
        return IdentityToken(token=SecretStr("identity-sentinel"), expires_at=time.time() + 3600)

    async def close(self):
        self.closed = True


def response_data(now=None):
    now = int(time.time()) if now is None else now

    def stamp(seconds):
        return (
            datetime.fromtimestamp(now + seconds, timezone.utc).isoformat().replace("+00:00", "Z")
        )

    return {
        "success": True,
        "data": {
            "protocolVersion": 1,
            "issuedAt": stamp(0),
            "context": {"installationId": "i", "applicationId": "a", "environmentId": "e"},
            "clientId": "client",
            "clientToken": "application-sentinel",
            "clientTokenExpiresAt": stamp(300),
            "configuration": {"DATABASE_URL": "secret-sentinel"},
            "refreshAfter": stamp(120),
            "expiresAt": stamp(900),
        },
    }


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in list(os.environ):
        if key.startswith(("MISO_", "REDIS_", "AZURE_")):
            monkeypatch.delenv(key)
    monkeypatch.setattr("miso_client.utils.config_loader._load_dotenv_if_available", lambda: None)


def azure_env(monkeypatch):
    monkeypatch.setenv("MISO_AUTH_MODE", "azure-managed-identity")
    monkeypatch.setenv("MISO_CONTROLLER_URL", "https://controller.test")
    monkeypatch.setenv("MISO_BOOTSTRAP_AUDIENCE", "api://broker")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [None, "local"])
async def test_local_existing_controller_no_azure_or_bootstrap(monkeypatch, mode):
    if mode:
        monkeypatch.setenv("MISO_AUTH_MODE", mode)
    monkeypatch.setenv("MISO_CLIENTID", "legacy-client")
    monkeypatch.setenv("MISO_CLIENTSECRET", "legacy-secret")
    monkeypatch.setenv("DATABASE_URL", "local-secret")
    identity = Identity()
    original_import = builtins.__import__

    def reject_azure(name, *args, **kwargs):
        assert not name.startswith("azure")
        return original_import(name, *args, **kwargs)

    seen = []

    def legacy_endpoint(request):
        seen.append(request.url.path)
        assert "bootstrap" not in request.url.path
        if request.url.path == "/api/v1/auth/token":
            assert request.headers["x-client-secret"] == "legacy-secret"
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "token": "legacy-token",
                    "expiresIn": 3600,
                    "expiresAt": "2030-01-01T00:00:00Z",
                },
            )
        assert request.headers["x-client-token"] == "legacy-token"
        return httpx.Response(200, json={"ok": True})

    original_client = httpx.AsyncClient
    with patch("builtins.__import__", side_effect=reject_azure), patch(
        "httpx.AsyncClient",
        side_effect=lambda **kw: original_client(
            transport=httpx.MockTransport(legacy_endpoint), **kw
        ),
    ):
        runtime = await init_secrets(token_provider=identity)
        assert runtime.secrets.require("DATABASE_URL") == "local-secret"
        assert runtime.context is None
        assert runtime.secrets.get("MISSING") is None
        result = await runtime.client._internal_http_client.get("/api/legacy")
        assert result == {"ok": True}
        assert seen == ["/api/v1/auth/token", "/api/legacy"]
        assert identity.calls == []
        await runtime.close()
        await runtime.close()
        with pytest.raises(BootstrapError, match="closed"):
            runtime.secrets.get("DATABASE_URL")


@pytest.mark.asyncio
async def test_local_aliases_dotenv_selection_and_snapshot(monkeypatch):
    monkeypatch.setenv("MISO_CLIENT_ID", "alias")
    monkeypatch.setenv("MISO_CLIENT_SECRET", "secret")

    def dotenv():
        monkeypatch.setenv("MISO_AUTH_MODE", "azure-managed-identity")
        monkeypatch.setenv("DATABASE_URL", "dotenv-secret")

    monkeypatch.setattr("miso_client.utils.config_loader._load_dotenv_if_available", dotenv)
    runtime = await init_secrets()
    assert runtime.client.config.client_id == "alias"
    monkeypatch.setenv("DATABASE_URL", "changed")
    assert runtime.secrets.require("DATABASE_URL") == "dotenv-secret"
    await runtime.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["typo", "", "Azure"])
async def test_unknown_mode_no_network(monkeypatch, mode):
    monkeypatch.setenv("MISO_AUTH_MODE", mode)
    with patch("httpx.AsyncClient", side_effect=AssertionError("no network")):
        with pytest.raises(BootstrapError, match="invalid-auth-mode"):
            await init_secrets()


@pytest.mark.asyncio
async def test_azure_missing_settings_never_reads_legacy(monkeypatch):
    monkeypatch.setenv("MISO_AUTH_MODE", "azure-managed-identity")
    monkeypatch.setenv("MISO_CLIENTSECRET", "legacy-secret")
    identity = Identity()
    with patch("miso_client.utils.bootstrap.load_config", side_effect=AssertionError("no local")):
        with pytest.raises(BootstrapError, match="invalid-azure-settings"):
            await init_secrets(token_provider=identity)
    assert identity.calls == []


@pytest.mark.asyncio
async def test_azure_token_only_actual_request_and_denial(monkeypatch):
    azure_env(monkeypatch)
    identity = Identity()
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("bootstrap"):
            assert json.loads(request.content) == {"protocolVersion": 1}
            assert request.headers["authorization"] == "Bearer identity-sentinel"
            assert "x-client-secret" not in request.headers
            return httpx.Response(200, json=response_data())
        assert request.headers["x-client-token"] == "application-sentinel"
        assert "identity-sentinel" not in str(request.headers)
        return httpx.Response(
            403, json={"code": "bootstrap_identity_disabled", "error": "secret-sentinel"}
        )

    original = httpx.AsyncClient
    with patch(
        "httpx.AsyncClient",
        side_effect=lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    ):
        injected = original(transport=httpx.MockTransport(handler))
        runtime = await init_secrets(token_provider=identity, http_client=injected)
        client = runtime.client
        assert client.config.client_secret is None
        assert runtime.secrets.require("DATABASE_URL") == "secret-sentinel"
        assert "secret-sentinel" not in repr(runtime)
        assert "application-sentinel" not in repr(client.config)
        assert "application_token_provider" not in client.config.model_dump()
        with pytest.raises(Exception, match="Managed runtime request failed"):
            await client._internal_http_client.get("/protected")
        with pytest.raises(BootstrapError, match="authorization-denied"):
            runtime.secrets.get("DATABASE_URL")
        with pytest.raises(BootstrapError):
            await client._internal_http_client.get("/protected")
        assert calls == ["/api/v1/auth/bootstrap", "/protected"]
        assert "DATABASE_URL" not in os.environ
        await runtime.close()
        assert not injected.is_closed and not identity.closed
        await injected.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 422, 302])
async def test_no_downgrade_or_retry_terminal_status(monkeypatch, status):
    azure_env(monkeypatch)
    identity = Identity()
    handler = AsyncMock(return_value=httpx.Response(status, text="secret-sentinel"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BootstrapError) as caught:
            await init_secrets(token_provider=identity, http_client=client)
        assert "secret-sentinel" not in str(caught.value)
        assert caught.value.__context__ is None
    assert handler.call_count == 1


@pytest.mark.asyncio
async def test_transient_retry_then_success():
    responses = [
        httpx.Response(503),
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json=response_data()),
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: responses.pop(0))
    ) as client:
        transport = BrokerTransport(
            "https://controller.test/api/v1/auth/bootstrap", "api://b", Identity(), client
        )
        with patch("miso_client.utils.bootstrap_transport.asyncio.sleep", new=AsyncMock()):
            body = await transport.fetch()
        assert parse_snapshot(body, time.time()).clientId == "client"
    assert not responses


def test_retry_after_bounds():
    assert retry_delay("10", 0) == 10
    with pytest.raises(BootstrapError):
        retry_delay("11", 0)
    assert 0 <= retry_delay("garbage", 0) <= 1


def test_legacy_configuration_json_schema_remains_available():
    from miso_client import MisoClientConfig

    schema = MisoClientConfig.model_json_schema()
    assert "client_secret" in schema["properties"]
    assert "application_token_provider" not in schema["properties"]
    assert "runtime_guard" not in schema["properties"]
