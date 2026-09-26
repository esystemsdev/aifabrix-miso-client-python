# Secret initialization with client credentials

Initialize the runtime at your application's async startup boundary, before constructing
connections that consume secrets:

```python
from miso_client import init_secrets

runtime = await init_secrets()
try:
    miso = runtime.client
    database_url = runtime.secrets.require("DATABASE_URL")
    optional_value = runtime.secrets.get("OPTIONAL_VALUE")
finally:
    await runtime.close()
```

## Configuration

Deploy with these process environment variables:

```dotenv
MISO_AUTH_MODE=client-credentials
MISO_CONTROLLER_URL=https://controller.example.test/miso
MISO_CLIENTID=your-application-client-id
MISO_CLIENTSECRET=your-application-client-secret
```

The deployment system supplies the application's credentials. The client uses only Miso
endpoints; it does not discover providers or access a secret storage service directly.
Bootstrap mode requires these canonical names; underscore credential aliases and dotenv
loading apply only to local mode. Missing or invalid settings fail before network access.
The controller URL must use HTTPS, with an optional deployment prefix such as `/miso`.
Userinfo, query strings, fragments and ambiguous paths are rejected. The client preserves
the prefix for both `/api/v1/auth/token` and `/api/v1/auth/bootstrap`.

The controller must support the client-token bootstrap endpoint before you enable this
mode. The token exchange returns HTTP 201 with a data envelope; bootstrap returns HTTP 200
with a validated snapshot. A deployment without that endpoint fails initialization.
There is no automatic fallback to local mode.

## Local mode

With `MISO_AUTH_MODE` absent or set to `local`, the SDK uses `load_config()` and the ordinary
token endpoint. Existing `MisoClient(config)` callers remain unchanged. Local mode supports
`MISO_CLIENT_ID`/`MISO_CLIENT_SECRET` aliases and normal dotenv loading. It captures local
configuration at startup and uses ordinary credential-based token renewal.
`runtime.context` is `None` locally; local settings are not verified identity claims.

The mode is selected before dotenv loading. A mode present only in dotenv cannot change
that selection. Other mode names fail with `invalid-auth-mode`.

## Rotation and recovery

A new bootstrap runtime exchanges credentials once. Each completely validated snapshot
provides the client token for subsequent refreshes; startup credentials are then released
from the transport. Changes to process environment variables do not redirect or reconfigure
a running bootstrap runtime.

Refresh occurs every 110–120 seconds. Credential rotation alone does not interrupt a healthy
runtime while its snapshot tokens remain accepted. After a failure that invalidates the
runtime, close it and initialize a fresh runtime with current deployment credentials,
usually by restarting the process. Authorization denial never triggers an automatic re-mint.

Normal API requests observe the snapshot's advertised 300-second token lifetime, reduced by
30 seconds. Secrets have a separate 900-second lifetime, also reduced by 30 seconds. A retained
snapshot token can authenticate bootstrap recovery until the secret deadline; it cannot
extend ordinary API token validity or secret access. This relies on the controller issuing
snapshot tokens with a 900-second actual lifetime. If recovery fails, requests fail safely.
Monotonic elapsed time prevents wall-clock rollback from extending those deadlines.

Authorization denial, invalid protocol/identity, expiration and shutdown invalidate the
runtime. Ordinary user authentication or business permission failures do not invalidate it.
A typed application-token expiry triggers a shared refresh without replaying the failed
application request. A new runtime is required after terminal invalidation.

## Confidentiality and cleanup

Credentials are sent only to the token endpoint. Bootstrap sends `x-client-token`; ordinary
API calls use the installed snapshot token. Requests remain pinned to the configured HTTPS
origin. Redirects and environment proxies are disabled. Responses must be uncompressed and
fit within 1 MiB. Each exchange has a 30-second total budget and 5-second attempts; transient
failures retry at most three times per step. HTTP 401/403 are terminal.

Snapshot configuration stays in private memory; it does not overwrite process environment,
credential settings, files or caches. `get(name)` returns `None` for an absent optional value;
`require(name)` rejects missing or empty values. Both reject invalid or closed runtime state.
Values copied into application code cannot be erased by the SDK. Never log credentials,
secret values or raw legacy config objects.

```python
def changed(keys):
    # Schedule replacement of affected connections; only key names are supplied.
    pass


def invalidated(reason):
    # Stop dependent connections; the reason contains no credential values.
    pass


unsubscribe = runtime.on_secrets_changed(changed)
unsubscribe_invalidated = runtime.on_invalidated(invalidated)
```

Callbacks run synchronously in registration order. Listener failures do not expose exception
values or prevent later listeners. Rebuild connections in your application's connection factory.
`close()` is awaitable, idempotent and bounded; saved client references also reject further
requests after invalidation.

Tests/hosts may inject `http_client=`. It must have `trust_env=False` and no event hooks, and
remains caller-owned. Bootstrap bypasses its default headers, auth, cookies, query parameters,
and base URL. Use a dedicated client with trusted TLS and transport configuration.

## Migration and rollout

Use `client-credentials` for remote bootstrap or `local` for ordinary environment-based
configuration. The previous provider adapter, provider token types, injection keyword and
optional dependency extra have been removed. Install the base `miso-client` package and remove
provider-specific imports/settings from application startup.

Deploy the compatible controller first, provision credentials, then enable bootstrap in the
application. Move import-time secret reads behind async initialization. Validate initialization,
refresh, permitted configuration access, denial and controller audit evidence before promotion.
The repeatable smoke test is documented in [manual tests](../tests/manual/README.md).

For rollback, use a previously tested SDK/controller combination in explicit `local` mode with
all required local configuration restored. Changing the mode alone cannot recreate secrets that
were only available remotely. Do not re-enable a removed provider mode against the new endpoint.
