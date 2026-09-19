# Secret initialization for local and Azure workloads

Use the same server-side startup code in both environments:

```python
from miso_client import init_secrets

runtime = await init_secrets()
try:
    miso = runtime.client
    database_url = runtime.secrets.require("DATABASE_URL")
    optional_value = runtime.secrets.get("OPTIONAL_VALUE")
    # Construct dependent connections here, after initialization.
finally:
    await runtime.close()
```

## Existing controllers and local development

With `MISO_AUTH_MODE` absent or set to `local`, initialization uses the existing
`load_config()` and ordinary Miso token endpoint. It makes no Azure identity or
bootstrap calls, imports no Azure package, and requires no controller upgrade.
Existing `MisoClient(config)` and `load_config()` callers continue to work unchanged.

Set the usual `MISO_CONTROLLER_URL`, `MISO_CLIENTID` and `MISO_CLIENTSECRET` values
(or the `MISO_CLIENT_ID` and `MISO_CLIENT_SECRET` aliases). Local dotenv loading
preserves process-environment precedence. Secret accessors use a startup snapshot of
the local environment; restart/reinitialize after changing local configuration.
`runtime.context` is `None` locally: local settings are not verified identity claims.
Normal local token renewal retains the existing behavior.

Mode is selected from the process environment **before** dotenv is loaded. A mode
value found only in dotenv cannot switch the selected provider. Unknown modes fail.
There is no automatic detection of Azure from a hostname or installed package.

## Opt-in Azure mode

The installed wheel is verified on Python 3.10–3.13. Python 3.8/3.9 currently fail
on an existing SDK type annotation despite the older package metadata minimum.
Use Python 3.10 or newer for this delivery. Install the optional adapter:

```bash
pip install 'miso-client[azure]'
```

Deployment supplies:

```dotenv
MISO_AUTH_MODE=azure-managed-identity
MISO_CONTROLLER_URL=https://your-installation-miso-host
MISO_BOOTSTRAP_AUDIENCE=api://your-miso-api-application-id
```

Use a system-assigned managed identity, or supply `AZURE_CLIENT_ID` for an assigned
user-managed identity. The controller must already implement the v1
`POST /api/v1/auth/bootstrap` broker and have an active binding for that identity.
This client change alone does not provide that controller capability.

Missing settings fail before identity acquisition. Explicit Azure mode never loads
local dotenv or falls back to legacy secrets, CLI/developer credentials or anonymous
access. An unavailable identity or older controller causes a safe initialization
failure; use local mode with existing credentials for an older controller.

Azure mode receives a Miso application token and permitted runtime secrets, never a
Miso client secret. The SDK renews through the broker and uses existing application
token transport on ordinary calls. Managed-token calls are pinned to the configured
HTTPS controller origin; cross-origin URLs, credential-bearing URLs and redirects
are rejected. Environment proxies are disabled for managed SDK HTTP clients.
The broker requests uncompressed JSON and rejects compressed responses before decoding. It does not read Key Vault or write remote secrets
into the process environment, files, Redis caches or diagnostics. Managed-app Miso
and Keycloak retain their separate platform startup; this helper is for workloads.

## Lifetimes, rotation and shutdown

The SDK refreshes at 110–120 seconds, treats the 300-second token and 900-second
snapshot as unusable 30 seconds early, and never extends those deadlines during an
outage. Expired tokens block Miso requests while still-valid configuration may remain
readable. Broker authorization denial, typed application identity/token rejection,
or a protocol/context change invalidates the runtime. Ordinary user authentication
and business permission errors leave the runtime valid. A typed application-token
expiry triggers one shared broker refresh without replaying the failed request;
rejected tokens cannot be reused if refresh fails. To recover an invalid runtime,
reinitialize explicitly after resolving the cause. Shutdown and invalidation prevent
further SDK requests and secret lookups, including through a saved client reference.

`require(name)` rejects absent or empty values. `get(name)` returns `None` for absent
optional values and preserves empty strings. Both fail on closed/invalid state.
Secrets already copied into application code cannot be erased or revoked by this SDK.
Do not log secrets or serialize legacy config objects that contain credentials.

```python
def changed(keys):
    # Only key names are supplied. Schedule replacement of affected connections.
    pass


def invalidated(reason):
    # Stop dependent connections. No credential values are supplied.
    pass


unsubscribe = runtime.on_secrets_changed(changed)
unsubscribe_invalidated = runtime.on_invalidated(invalidated)
```

Callbacks run synchronously in registration order; failures do not stop later
listeners and their error values are not logged. Rebuild database/Redis clients in
your existing connection factory when notified. The SDK does not silently mutate
those clients or revoke database passwords. `close()` is awaitable and idempotent,
with bounded cleanup of SDK-owned resources. An injected identity provider or broker
HTTP client remains caller-owned.

## Verification and rollout

Mocked tests cover legacy requests, no Azure access in local mode, v1 response
validation, token-only requests, denial, expiry, retries, concurrency and cleanup.
The initial SDK fixtures are synthetic tests of the published plan contract; canonical
controller fixtures and live cross-RG identity/no-vault proof remain rollout checks.
Record compatible controller, client and workload versions before enabling Azure mode.
An SDK upgrade on its own does not migrate import-time secret reads: move those reads
behind the existing async startup boundary.
