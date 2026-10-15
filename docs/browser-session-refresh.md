# Browser-session cookie refresh

A browser that opens a consumer API link directly (for example a Dataplane
`/api/v1/rest/<system>/docs` page) sends only the `miso_access_token` cookie. That
cookie holds a Keycloak access token that lives about five minutes. Miso keeps the
refresh token server-side, keyed by that access token, and renews the cookie on
bodyless `POST /api/v1/auth/refresh`. The browser UI calls that endpoint itself; a
direct link has no UI code, so the server has to.

`MisoClient.validate_or_refresh_session_cookie(token)` makes that call for you.

## Usage (FastAPI)

```python
from fastapi import HTTPException, Request, Response
from miso_client import apply_session_cookie

async def current_user(request: Request, response: Response):
    token = client.get_session_cookie_token(request)  # cookie only, never Bearer
    result = await client.validate_or_refresh_session_cookie(token)
    if not result.valid:
        raise HTTPException(status_code=401)
    apply_session_cookie(response, result)  # adds Set-Cookie only when renewed
    return result.user  # use result.token for downstream calls
```

## Behaviour

| Situation | Result |
| --- | --- |
| Token not expired, valid | `valid=True`, same token, no refresh |
| Token not expired, invalid (signature, revoked, issuer) | `valid=False`, no refresh |
| Token expired (or within 30 s of `exp`), session alive | One refresh; `valid=True`, new token, `set_cookie` set, `refreshed=True` |
| Token expired, Miso session ended (30 min idle) | `valid=False` (Miso answers "No active browser session"); user logs in again |
| Token without a readable `exp` | Never refreshed |

- **One refresh per expired token.** Concurrent requests with the same expired cookie
  share one refresh. Miso deletes the old session when it rotates, so the renewed
  session is remembered in-process until the new token expires; later requests that
  still carry the old cookie get the same new token and `Set-Cookie`.
- **Security.** Token values are never logged; in-process keys are SHA-256 digests of
  the old token. The refresh uses a short-lived HTTP client, so the renewed cookie never
  lands in the SDK's shared cookie jar. `Cookie` and `Set-Cookie` headers are masked in
  HTTP audit logs. Token fields are excluded from model `repr`.
- **Set-Cookie** is passed through verbatim, keeping Miso's attributes (`Path=/`,
  `HttpOnly`, `SameSite=Lax`, `Secure` in production).

## Limits

- **Multiple replicas.** The memo is per process. If two replicas refresh the same
  cookie at the same moment, one of them gets "No active browser session" and that
  single request returns 401; a reload recovers.
- **Rate limit.** Miso limits `/auth/refresh` per caller IP (20 per 15 minutes) when
  rate limiting is enabled. All refreshes from one consumer share its IP, so keep
  `DISABLE_RATE_LIMIT=true` (the deploy default) or raise the limit before relying on
  this with many concurrent users.

## Parity

The TypeScript SDK (`aifabrix-miso-client`) should expose the same behaviour; that is
a separate follow-up. Consumers (for example Dataplane) call
`validate_or_refresh_session_cookie` for cookie tokens and apply `set_cookie`.
