"""Plan 52.0 regressions through real SDK layers; only HTTP I/O is substituted.

These acceptance tests exercise fallback and diagnostic preservation without
mocking InternalHttpClient.request/post.
"""

from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from typing import Any, Literal
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio

from miso_client import MisoClient
from miso_client.errors import ConnectionError, EncryptionError, MisoClientError
from miso_client.models.bootstrap import ApplicationTokenProvider
from miso_client.models.config import AuditConfig, AuthMethod, AuthStrategy, MisoClientConfig
from miso_client.utils.client_token_manager import ClientTokenManager
from miso_client.utils.error_utils import extract_correlation_id_from_error

ENDPOINT = "/api/security/parameters/encrypt"
CORRELATION = "52-auth-contract-correlation"


def problem(status: int = 401) -> dict[str, Any]:
    """Controller diagnostic fields, with synthetic values only."""
    return {
        "type": "https://controller.test/problems/auth",
        "title": "Unauthorized",
        "status": status,
        "code": "auth_method_rejected",
        "detail": "The selected authentication method was refused",
        "authMethod": "client-token",
        "clientIdentity": {"applicationId": "synthetic-test-app"},
        "instance": ENDPOINT,
        "correlationId": CORRELATION,
    }


class Wire:
    """Observe outgoing HTTP requests without replacing any SDK request method."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.respond: Callable[[httpx.Request], httpx.Response] = lambda _: httpx.Response(
            200, json={"ok": True}
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)


@pytest.fixture
def wire() -> Wire:
    return Wire()


@pytest_asyncio.fixture(params=[False, True], ids=["local", "managed"])
async def sdk(
    request: pytest.FixtureRequest, wire: Wire, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[MisoClient]:
    provider = AsyncMock(spec=ApplicationTokenProvider) if request.param else None
    if provider is not None:
        provider.get_token.return_value = "synthetic-client-token"
    config = MisoClientConfig(
        controller_url="https://controller.test",
        client_id="synthetic-client",
        client_secret=None if provider is not None else "synthetic-secret",
        application_token_provider=provider,
        encryption_key="synthetic-encryption-key",
        cache={"encryptionCacheTTL": 0},
        audit=AuditConfig(enabled=False),
    )
    client = MisoClient(config)
    internal = client.http_client.get_internal_client()
    internal.client = httpx.AsyncClient(
        base_url=config.controller_url, transport=httpx.MockTransport(wire.handle)
    )
    internal.token_manager.client_token = "synthetic-client-token"
    internal.token_manager.token_expires_at = datetime.now() + timedelta(hours=1)
    # Local 401 handling invalidates the token. Keep subsequent mint I/O offline,
    # while retaining the token manager and all request/error conversion logic.
    monkeypatch.setattr(
        ClientTokenManager,
        "_create_temp_client",
        lambda *_: httpx.AsyncClient(
            base_url=config.controller_url,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    201,
                    json={
                        "token": "synthetic-client-token",
                        "expiresIn": 3600,
                        "expiresAt": "2099-01-01T00:00:00Z",
                    },
                )
            ),
        ),
    )
    try:
        yield client
    finally:
        await client.disconnect()


def method_on_wire(request: httpx.Request) -> str:
    return "bearer" if request.headers.get("authorization") else "client-token"


@pytest.mark.parametrize("order", [("bearer", "client-token"), ("client-token", "bearer")])
@pytest.mark.parametrize("verb", ["GET", "POST"])
async def test_401_falls_back_through_transport(
    sdk: MisoClient, wire: Wire, order: tuple[AuthMethod, AuthMethod], verb: Literal["GET", "POST"]
) -> None:
    """The second configured method must run after a real HTTP 401 conversion."""
    wire.respond = lambda req: (
        httpx.Response(401, json=problem())
        if method_on_wire(req) == order[0]
        else httpx.Response(200, json={"ok": True})
    )
    result = await sdk.request_with_auth_strategy(
        verb, ENDPOINT, AuthStrategy(methods=list(order), bearerToken="synthetic-bearer")
    )
    assert result == {"ok": True}
    assert [method_on_wire(req) for req in wire.requests] == list(order)


async def test_default_strategy_reaches_client_token_only_endpoint(
    sdk: MisoClient, wire: Wire
) -> None:
    """Record the SDK's automatic controller token header, even on bearer attempts."""
    wire.respond = lambda req: httpx.Response(
        200 if req.headers.get("x-client-token") else 401, json={"ok": True}
    )
    result = await sdk.http_client.get_internal_client().authenticated_request(
        "POST", ENDPOINT, "synthetic-bearer"
    )
    assert result == {"ok": True}
    assert len(wire.requests) == 1
    assert wire.requests[0].headers["x-client-token"] == "synthetic-client-token"


@pytest.mark.parametrize("status", [403, 422, 500])
async def test_non_401_does_not_try_another_method(
    sdk: MisoClient, wire: Wire, status: int
) -> None:
    wire.respond = lambda _: httpx.Response(status, json=problem(status))
    with pytest.raises(MisoClientError) as caught:
        await sdk.request_with_auth_strategy(
            "POST", ENDPOINT, AuthStrategy(methods=["bearer", "client-token"], bearerToken="test")
        )
    assert caught.value.status_code == status
    assert len(wire.requests) == 1


async def test_transport_failure_does_not_try_another_method(sdk: MisoClient, wire: Wire) -> None:
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic connection failure", request=request)

    wire.respond = offline
    with pytest.raises(ConnectionError):
        await sdk.request_with_auth_strategy(
            "POST", ENDPOINT, AuthStrategy(methods=["bearer", "client-token"], bearerToken="test")
        )
    assert len(wire.requests) == 1


async def test_exhausted_methods_preserve_last_diagnostic(sdk: MisoClient, wire: Wire) -> None:
    wire.respond = lambda _: httpx.Response(401, json=problem())
    with pytest.raises(MisoClientError) as caught:
        await sdk.request_with_auth_strategy(
            "POST", ENDPOINT, AuthStrategy(methods=["bearer", "client-token"], bearerToken="test")
        )
    assert [method_on_wire(req) for req in wire.requests] == ["bearer", "client-token"]
    assert caught.value.status_code == 401
    assert caught.value.auth_method == "client-token"
    assert caught.value.error_body is not None
    assert caught.value.error_body["correlationId"] == CORRELATION


@pytest.mark.parametrize("operation", ["encrypt", "decrypt"])
@pytest.mark.parametrize(
    "field", ["code", "detail", "auth_method", "correlation", "identity", "instance"]
)
async def test_encryption_preserves_controller_diagnostics(
    sdk: MisoClient, wire: Wire, operation: str, field: str
) -> None:
    """Each diagnostic has its own assertion so one lost field cannot hide another."""
    body = problem()
    wire.respond = lambda _: httpx.Response(401, json=body)
    with pytest.raises(EncryptionError) as caught:
        if operation == "encrypt":
            await sdk.encryption.encrypt("synthetic-plaintext", "test-parameter")
        else:
            await sdk.encryption.decrypt("enc://synthetic-ciphertext", "test-parameter")
    error = caught.value
    assert error.status_code == 401
    assert error.parameter_name == "test-parameter"
    payload = error.error_body or {}
    actual = {
        "code": error.code,
        "detail": payload.get("detail"),
        "auth_method": error.auth_method,
        "correlation": extract_correlation_id_from_error(error) or payload.get("correlationId"),
        "identity": payload.get("clientIdentity"),
        "instance": payload.get("instance"),
    }
    expected = {
        "code": body["code"],
        "detail": body["detail"],
        "auth_method": body["authMethod"],
        "correlation": CORRELATION,
        "identity": body["clientIdentity"],
        "instance": body["instance"],
    }
    assert actual[field] == expected[field]


@pytest.mark.parametrize("operation", ["encrypt", "decrypt"])
async def test_structured_error_and_header_correlation_survive(
    sdk: MisoClient, wire: Wire, operation: str
) -> None:
    body = {
        "errors": ["Synthetic permission denial"],
        "type": "/Errors/Unauthorized",
        "title": "Unauthorized",
        "statusCode": 401,
        "authMethod": "client-token",
    }
    wire.respond = lambda _: httpx.Response(
        401, json=body, headers={"x-correlation-id": CORRELATION}
    )
    with pytest.raises(EncryptionError) as caught:
        await getattr(sdk.encryption, operation)("synthetic-value", "test-parameter")
    assert caught.value.error_response is not None
    assert caught.value.error_response.errors == body["errors"]
    assert caught.value.auth_method == "client-token"
    assert extract_correlation_id_from_error(caught.value) == CORRELATION


async def test_preserved_diagnostics_do_not_expose_secret_fields(
    sdk: MisoClient, wire: Wire
) -> None:
    body = problem()
    body["clientSecret"] = "DO-NOT-EXPOSE-synthetic-secret"
    wire.respond = lambda _: httpx.Response(401, json=body)
    with pytest.raises(EncryptionError) as caught:
        await sdk.encryption.encrypt("synthetic-plaintext", "test-parameter")
    visible = str(caught.value) + repr(caught.value.error_body) + repr(caught.value.error_response)
    assert "DO-NOT-EXPOSE-synthetic-secret" not in visible


@pytest.mark.parametrize("code", ["bootstrap_token_invalid", "bootstrap_token_expired"])
async def test_bootstrap_denials_never_replay_with_another_method(
    sdk: MisoClient, wire: Wire, code: str
) -> None:
    body = problem()
    body["code"] = code
    wire.respond = lambda _: httpx.Response(401, json=body)
    with pytest.raises(MisoClientError) as caught:
        await sdk.request_with_auth_strategy(
            "POST", ENDPOINT, AuthStrategy(methods=["bearer", "client-token"], bearerToken="test")
        )
    assert len(wire.requests) == 1
    assert (caught.value.error_body or {}).get("code") == code


@pytest.mark.parametrize("content_type", ["application/json", "application/problem+json"])
async def test_echoed_credentials_are_redacted_from_all_diagnostics(
    sdk: MisoClient, wire: Wire, content_type: str
) -> None:
    body = problem()
    body["detail"] = "Rejected synthetic-client-token using synthetic-encryption-key"
    body["clientIdentity"] = {
        "applicationId": "synthetic-app",
        "clientSecret": "hidden-test-secret",
    }
    body["title"] = "Failure hidden-test-secret"
    body.pop("correlationId")
    wire.respond = lambda _: httpx.Response(
        401,
        json=body,
        headers={"content-type": content_type, "x-correlation-id": "synthetic-client-token"},
    )
    with pytest.raises(EncryptionError) as caught:
        await sdk.encryption.encrypt("synthetic-plaintext", "test-parameter")
    error = caught.value
    visible = (
        str(error) + repr(error.error_body) + repr(error.error_response) + str(error.correlation_id)
    )
    for secret in ("synthetic-client-token", "synthetic-encryption-key", "hidden-test-secret"):
        assert secret not in visible
    assert error.auth_method == "client-token"
    assert error.code == "auth_method_rejected"


async def test_body_status_cannot_turn_forbidden_into_auth_retry(
    sdk: MisoClient, wire: Wire
) -> None:
    wire.respond = lambda _: httpx.Response(403, json=problem(401))
    with pytest.raises(MisoClientError) as caught:
        await sdk.request_with_auth_strategy(
            "POST", ENDPOINT, AuthStrategy(methods=["bearer", "client-token"], bearerToken="test")
        )
    assert caught.value.status_code == 403
    assert len(wire.requests) == 1
