---
name: Client token and token exchange
overview: "Align the Python SDK with miso-controller auth policy: document and harden that all controller APIs require x-client-token (only the client token endpoint accepts client id/secret), and add user token exchange (Entra/delegated to Keycloak) so apps can exchange external tokens and use the effective token for subsequent calls."
todos: []
isProject: false
---

# Client token policy and user token exchange (Python SDK)

## Context

- **Controller policy**: All miso-controller APIs require a **client token** sent as `x-client-token`. The only endpoint that accepts `x-client-id` and `x-client-secret` is the client token endpoint (e.g. `POST /api/v1/auth/token`). No other API may receive client id/secret directly.
- **Controller plan 156** ([unified_token_validation_and_exchange](file:///workspace/aifabrix-miso/.cursor/plans/156-unified_token_validation_and_exchange.plan.md)): The controller will accept Bearer tokens that are either Keycloak or delegated (e.g. Entra). For delegated tokens it will validate and exchange internally, returning the effective Keycloak token in response headers (`X-Auth-Token`, `X-Token-Exchanged`). The controller also exposes an explicit exchange endpoint: `POST /api/v1/auth/token/exchange` (delegated token in Bearer, Keycloak token in response body).

The Python SDK already uses client token correctly (fetches once with client id/secret, then sends only `x-client-token` for all other requests). This plan adds explicit documentation, optional hardening, and **user token exchange** so apps that have an Entra (or other delegated) token can exchange it for a Keycloak token and use it with the SDK.

---

## Rules and Standards

This plan must comply with the following rules from [Project Rules](.cursor/rules/project-rules.mdc):

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** – HTTP client pattern, token management (client token vs user token), API endpoints; token exchange reuses `authenticated_request` and client token flow.
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** – Python conventions, type hints, error handling, async/await, Google-style docstrings for all public methods.
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** – Files ≤500 lines, methods ≤20–30 lines; new `exchange_token` and response types stay small.
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** – pytest, pytest-asyncio, mock HttpClient/httpx; unit tests for token exchange (success/error, headers); ≥80% coverage for new code.
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** – Never log or expose client id/secret; only client token endpoint receives credentials; mask sensitive data in logs; x-client-token (lowercase).
- **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** – Error handling (try/except, return defaults or raise from HTTP layer); HTTP client usage; token handling.
- **[When Adding New Features](.cursor/rules/project-rules.mdc#when-adding-new-features)** – Update models first if needed, expose via `miso_client/__init__.py`, write tests, update docs.

**Key Requirements**:

- Only the client token endpoint may receive `x-client-id` and `x-client-secret`; all other requests use `x-client-token`.
- Use `authenticated_request()` for the token exchange call so client token is applied automatically.
- Add type hints and Google-style docstrings for `exchange_token` and `TokenExchangeResponse`.
- Unit tests: mock HTTP; assert request has `x-client-token` and `Authorization: Bearer <delegated_token>`; assert response parsing.
- Keep new code under file/method size limits; handle errors per project patterns (log, structured errors, no uncaught raises from service layer where appropriate).

---

## Before Development

- Read [Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns) (HTTP client, token management) and [Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines).
- Review existing [AuthApi](miso_client/api/auth_api.py) and [ClientTokenManager](miso_client/utils/client_token_manager.py) for patterns.
- Confirm controller token exchange endpoint path and response shape (e.g. `POST /api/v1/auth/token/exchange`, body with `access_token` or `token`).
- Review [Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions) for mocking HttpClient and async methods (AsyncMock).

---

## Goals

1. **Client token policy**: Document and enforce that only the client token endpoint receives `x-client-id` / `x-client-secret`; all other API calls use `x-client-token` only.
2. **User token exchange**: Add support for the controller’s token exchange endpoint so callers can pass an Entra (or other delegated) token and receive a Keycloak token for subsequent authenticated calls.
3. **Optional**: Prepare for controller plan 156 by documenting that, once the controller returns `X-Auth-Token` / `X-Token-Exchanged`, the SDK could expose these for caching (implementation can follow in a later phase).

---

## Current state (SDK)

- [ClientTokenManager](miso_client/utils/client_token_manager.py) fetches the client token via `POST` to `config.clientTokenUri` (default `/api/v1/auth/token`) with headers `x-client-id` and `x-client-secret` only. No other code path sends client id/secret.
- [InternalHttpClient](miso_client/utils/internal_http_client.py) ensures `x-client-token` is set for all requests via `_ensure_client_token()` and never adds client id/secret to the main client or to arbitrary requests.
- There is **no** token exchange API in the SDK (no call to `/api/v1/auth/token/exchange`). Users with an Entra token have no SDK helper to exchange it for Keycloak.

**Existing test suites**: [tests/integration](tests/integration) and [tests/manual](tests/manual) are working correctly. This plan extends them only if needed (e.g. token exchange or client-token policy coverage); existing tests must continue to pass and must not be broken.

---

## Implementation plan

### 1. Document and harden client token policy

**Files:** [.cursorrules](.cursorrules), [.cursor/rules/project-rules.mdc](.cursor/rules/project-rules.mdc), [docs/backend-client-token.md](docs/backend-client-token.md), and optionally [miso_client/utils/client_token_manager.py](miso_client/utils/client_token_manager.py).

- Add a short “Client token only” policy to project rules and README/docs:
  - All controller APIs (except the client token endpoint) require `x-client-token`.
  - Only the configured client token URI may receive `x-client-id` and `x-client-secret`; the SDK must never send client id/secret to any other path.
- In `ClientTokenManager.fetch_client_token()`, add a comment above the temporary client that states this is the **only** place where client id/secret are sent.
- Optionally: in config or client initialization, document (e.g. in docstrings) that `client_id` and `client_secret` are used solely for obtaining the client token.

No change to runtime behavior is required; the SDK already complies. This is documentation and clarity.

---

### 2. Add user token exchange API

**Files:** New or existing auth API module, HTTP client usage, and public API surface.

- **Endpoint**: Use the controller’s token exchange endpoint. From plan 156 and typical patterns this is `POST /api/v1/auth/token/exchange` with:
  - **Request**: `Authorization: Bearer <delegated_token>` (e.g. Entra token); client token must also be sent (`x-client-token`) so the controller accepts the request.
  - **Response**: Body contains the new Keycloak token (e.g. `access_token` or `token`); optionally headers `X-Auth-Token`, `X-Token-Exchanged` once the controller implements plan 156.
- **SDK changes**:
  - Add a method to call this endpoint (e.g. `exchange_token(delegated_token: str)` or `auth_api.exchange_token(delegated_token: str)`). It should use the existing HTTP client so that:
    - Client token is automatically included (`x-client-token`).
    - The delegated token is sent as `Authorization: Bearer <delegated_token>`.
  - Define a small response type (e.g. `TokenExchangeResponse`) with at least the effective token (Keycloak); optionally `token_exchanged: bool` and any other fields the controller returns in body or that we can derive from headers.
  - Expose this on the public API (e.g. `MisoClient` and/or `AuthApi`) so apps can do:
    - Get Entra token → call `exchange_token(entra_token)` → use returned Keycloak token for `authenticated_request` / auth API calls.
- **Placement**: Implement in the same layer as other auth calls (e.g. [AuthApi](miso_client/api/auth_api.py) if that’s where validate/login live, or a dedicated small module). Reuse `HttpClient.authenticated_request` with the delegated token for the exchange request so client token is still applied by the internal client.
- **Config**: Use the same base URL and client token as for other API calls. No new config keys required unless the controller exposes a different path per environment; then consider an optional `tokenExchangeUri` (default `"/api/v1/auth/token/exchange"`).

---

### 3. Response headers (X-Auth-Token, X-Token-Exchanged) – optional / later

- Once the controller implements plan 156 and returns `X-Auth-Token` and `X-Token-Exchanged` on authenticated responses, the SDK could:
  - In `exchange_token`, if the controller returns these headers, map them into `TokenExchangeResponse` (e.g. `effective_token`, `token_exchanged`).
  - In a later phase, optionally expose these headers from other authenticated calls (e.g. via a wrapper or callback) so callers can cache the effective Keycloak token when they pass a delegated token. This is not required for the first version of this plan.

---

### 4. Documentation updates

**Files:** [README.md](README.md), [docs/backend-client-token.md](docs/backend-client-token.md), and any auth-focused doc.

- **Two-token model**:
  - **Client token**: Obtained once from the client token endpoint using client id/secret; sent as `x-client-token` on all other API requests. Only the client token endpoint receives client id/secret.
  - **User token**: Sent as `Authorization: Bearer <token>` for user-scoped operations; may be Keycloak or, after exchange, the result of exchanging an Entra/delegated token.
- **Token exchange**: Describe that when the user has an Entra (or other delegated) token, the app can call `exchange_token(delegated_token)` to get a Keycloak token and then use that for subsequent SDK calls. Mention that the controller may also perform transparent exchange (plan 156) and return the effective token in headers.

---

### 5. Tests

- **Unit**:
  - `ClientTokenManager`: Already covered; optionally add a test that no other code path sends client id/secret (e.g. assert request headers in mocked HTTP calls for non-token endpoints).
  - **Token exchange**: Mock HTTP client; call `exchange_token(entra_token)`; assert request uses `x-client-token` (from existing client token flow) and `Authorization: Bearer <entra_token>`; assert response parsing and that the returned type contains the effective token (and optionally `token_exchanged` if present).
- **Integration** ([tests/integration](tests/integration)): Existing integration tests are working correctly. Extend only if needed (e.g. add a test that calls `exchange_token` against a real controller when token exchange is available). Do not break or remove existing integration tests.
- **Manual** ([tests/manual](tests/manual)): Existing manual tests are working correctly. Extend only if needed (e.g. add a manual check for token exchange flow). Do not break or remove existing manual tests.

---

## Out of scope (for this plan)

- Implementing controller-side plan 156 (that’s the miso-controller repo).
- Changing how the SDK obtains or refreshes the **client** token (already correct).
- Adding optional hooks/callbacks for capturing `X-Auth-Token` from every authenticated response (can be a follow-up).

---

## Definition of done

Before marking this plan complete:

1. **Client token policy**: Documented in project rules and docs; code comment in `ClientTokenManager` states that client id/secret are used only for the client token endpoint.
2. **Token exchange**: `exchange_token(delegated_token)` (or equivalent) is implemented, uses `x-client-token` plus Bearer delegated token, and returns a structured response with the Keycloak token (and optional `token_exchanged` if controller provides it).
3. **Public API**: `MisoClient` and/or `AuthApi` exposes the exchange method; README and docs describe the two-token model and the exchange flow.
4. **Tests**: Unit tests for token exchange (and optionally for “no client id/secret on non-token endpoints”); extend [tests/integration](tests/integration) and [tests/manual](tests/manual) only if needed; existing integration and manual tests must continue to work. New code has ≥80% coverage.
5. **No breaking changes**: Existing client token or authenticated request behavior unchanged.
6. **Lint**: Run `ruff check` and `mypy` (must pass with zero errors/warnings).
7. **Format**: Run `black` and `isort` (code must be formatted).
8. **Test**: Run `pytest` AFTER lint/format (all tests must pass).
9. **Validation order**: LINT → FORMAT → TEST (mandatory sequence; never skip steps).
10. **Code quality**: Files ≤500 lines, methods ≤20–30 lines; type hints and Google-style docstrings on all new public methods; no hardcoded secrets; ISO 27001/data masking respected.
11. **Documentation**: README and/or docs updated for two-token model and token exchange usage.

---

## Summary diagram

```mermaid
sequenceDiagram
  participant App
  participant SDK
  participant Controller

  Note over App,Controller: "Client token (already in place)"
  App->>SDK: "MisoClient(config with client_id/secret)"
  SDK->>Controller: "POST /api/v1/auth/token (x-client-id, x-client-secret)"
  Controller-->>SDK: client token
  SDK->>SDK: cache client token

  Note over App,Controller: "User token exchange (new)"
  App->>SDK: "exchange_token(entra_token)"
  SDK->>Controller: "POST /api/v1/auth/token/exchange (x-client-token + Bearer entra_token)"
  Controller-->>SDK: "Keycloak token (body; later headers)"
  SDK-->>App: "TokenExchangeResponse(access_token, token_exchanged?)"

  App->>SDK: "authenticated_request(..., keycloak_token)"
  SDK->>Controller: "request (x-client-token + Bearer keycloak_token)"
  Controller-->>SDK: response
  SDK-->>App: result
```



---

## Plan Validation Report

**Date**: 2025-03-06
**Plan**: .cursor/plans/36-client_token_and_token_exchange.plan.md
**Status**: VALIDATED

### Plan Purpose

Align the Python SDK with miso-controller auth policy: (1) document and harden that all controller APIs require x-client-token and only the client token endpoint accepts client id/secret, and (2) add user token exchange (Entra/delegated to Keycloak) so apps can exchange external tokens and use the effective token for subsequent calls. **Scope**: ClientTokenManager, AuthApi/HTTP client, public API, docs, tests. **Type**: Development (auth/token feature) and documentation. **Components**: client token policy docs, `exchange_token` API, `TokenExchangeResponse` type, unit tests, README/docs.

### Applicable Rules

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** – HTTP client and token management; token exchange reuses authenticated_request and client token flow.
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** – Type hints, docstrings, error handling, async/await.
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** – Files ≤500 lines, methods ≤20–30 lines (mandatory for all plans).
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** – pytest, pytest-asyncio, mock HttpClient/httpx, ≥80% coverage for new code (mandatory for all plans).
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** – Client id/secret only on token endpoint; x-client-token lowercase; no logging of secrets (mandatory for all plans).
- **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** – Error handling, HTTP client usage.
- **[When Adding New Features](.cursor/rules/project-rules.mdc#when-adding-new-features)** – Models, public API export, tests, docs.

### Rule Compliance

- DoD requirements: Documented (lint: ruff + mypy; format: black + isort; test: pytest; order: LINT → FORMAT → TEST; file/method size; type hints; docstrings; security; documentation).
- Architecture Patterns: Compliant (plan uses authenticated_request, client token only on token endpoint).
- Code Style: Compliant (plan requires type hints and Google-style docstrings for new methods).
- Code Size Guidelines: Compliant (plan keeps new code small; DoD references file/method limits).
- Testing Conventions: Compliant (unit tests for exchange_token; DoD requires ≥80% coverage for new code).
- Security Guidelines: Compliant (client token policy and no client id/secret on other APIs explicitly in plan and rules).

### Plan Updates Made

- Added **Rules and Standards** section with links to project-rules.mdc (Architecture Patterns, Code Style, Code Size Guidelines, Testing Conventions, Security Guidelines, Common Patterns, When Adding New Features) and key requirements.
- Added **Before Development** checklist (read rules, review AuthApi/ClientTokenManager, confirm controller endpoint, review testing conventions).
- Expanded **Definition of Done** with: lint (ruff, mypy), format (black, isort), test (pytest), validation order (LINT → FORMAT → TEST), code quality (file/method size, type hints, docstrings, security), documentation, and ≥80% coverage for new code.
- Appended this **Plan Validation Report**.

### Recommendations

- When implementing, run `ruff check` and `mypy` first; fix any issues before running `black` and `isort`, then run `pytest`.
- In token exchange unit tests, use `AsyncMock` for `authenticated_request` and assert both `x-client-token` (from client token flow) and `Authorization: Bearer <delegated_token>` on the request.
- If the controller returns camelCase in the exchange response body (e.g. `accessToken`, `tokenExchanged`), parse into a Pydantic model with appropriate aliases so the public API can expose snake_case to Python callers.
- Keep [tests/integration](tests/integration) and [tests/manual](tests/manual) working correctly; extend them only if needed for token exchange or client-token policy, and do not break existing tests.

---

## Implementation Validation Report

**Date**: 2025-03-06  
**Status**: IMPLEMENTATION VALIDATED

### 1. Client token policy (documentation and hardening)


| Requirement                                 | Status | Evidence                                                                                                                                                                                              |
| ------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Client token only" policy in project rules | Done   | `.cursorrules` and `.cursor/rules/project-rules.mdc`: "Only the configured client token URI may receive x-client-id and x-client-secret; the SDK must never send client id/secret to any other path." |
| Code comment in ClientTokenManager          | Done   | `miso_client/utils/client_token_manager.py` lines 116–119: "This is the ONLY place where x-client-id and x-client-secret are sent."                                                                   |
| Docs (backend-client-token.md)              | Done   | Client token policy and token exchange section with two-token model and exchange flow.                                                                                                                |


### 2. User token exchange API


| Requirement                                            | Status | Evidence                                                                                                                    |
| ------------------------------------------------------ | ------ | --------------------------------------------------------------------------------------------------------------------------- |
| `exchange_token(delegated_token)`                      | Done   | `AuthApi.exchange_token()`, `AuthService.exchange_token()`, `MisoClient.exchange_token()`                                   |
| Uses `authenticated_request` (x-client-token + Bearer) | Done   | AuthApi and AuthService call `http_client.authenticated_request("POST", TOKEN_EXCHANGE_ENDPOINT, delegated_token, ...)`     |
| Endpoint `POST /api/v1/auth/token/exchange`            | Done   | `AuthApi.TOKEN_EXCHANGE_ENDPOINT = "/api/v1/auth/token/exchange"`                                                           |
| `TokenExchangeResponse` (accessToken, tokenExchanged?) | Done   | `miso_client/api/types/auth_types.py`: accessToken, tokenExchanged; validator accepts `token` or `accessToken`              |
| Public API (MisoClient, AuthApi)                       | Done   | `MisoClient.exchange_token()`, `client.api_client.auth.exchange_token()`; `TokenExchangeResponse` exported in `__init__.py` |


### 3. Documentation


| Requirement                            | Status | Evidence                                                                                            |
| -------------------------------------- | ------ | --------------------------------------------------------------------------------------------------- |
| Two-token model in README              | Done   | README: "Two-token model" and "Token exchange (Entra/delegated tokens)" with `exchange_token` usage |
| backend-client-token.md token exchange | Done   | Section "Token exchange (user tokens)" with example and note on x-client-token + Bearer             |


### 4. Tests


| Requirement                                                | Status | Evidence                                                                                                               |
| ---------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------- |
| Unit tests for token exchange                              | Done   | `tests/unit/test_auth_api.py`: test_exchange_token_success, _with_data_wrapper, _accepts_token_field, _error           |
| Assert request (POST, endpoint, token, auto_refresh=False) | Done   | test_exchange_token_success asserts call_args for POST, TOKEN_EXCHANGE_ENDPOINT, delegated token                       |
| Integration test for exchange                              | Done   | `tests/integration/test_api_endpoints.py`: test_exchange_token (skips when no delegated token or endpoint unavailable) |
| Existing tests not broken                                  | Done   | make test: 1322 passed                                                                                                 |


### 5. Definition of done checklist

1. Client token policy documented; code comment in ClientTokenManager — Done
2. Token exchange implemented with x-client-token + Bearer; structured response — Done
3. Public API and docs — Done
4. Unit tests for exchange; integration extended; ≥80% coverage — Done (93% total)
5. No breaking changes — Done
6. Lint (ruff): passed
7. Format (black, isort): passed (one file reformatted)
8. Test (pytest): 1322 passed
9. Validation order LINT → FORMAT → TEST — Followed
10. Code quality (file/method size, type hints, docstrings) — Compliant
11. Documentation — README and backend-client-token updated

### Optional / not in scope

- Optional `tokenExchangeUri` config: not added (plan allows default path only for first version).  
- X-Auth-Token / X-Token-Exchanged headers: documented as optional/later; response type has `tokenExchanged` for when controller provides it.

