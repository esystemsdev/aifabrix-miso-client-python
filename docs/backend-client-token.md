# Backend client-token endpoint for any app

This page shows minimal backend code you can add to **any** Python app so the frontend can get a client token (and optional DataClient config) from a single route. The SDK handles:

- **Token issuance** – your server calls the Miso Controller with client credentials and returns the token to the client.
- **Origin validation (CORS)** – optional; reject requests whose `Origin`/`Referer` is not in an allow list.
- **Audit logging** – request, success, failure, and origin validation failures are logged.

---

## Environment variables

Create a `.env` in your project (or set in your environment):

```env
# Required
MISO_CLIENTID=your-client-id
MISO_CLIENTSECRET=your-client-secret
MISO_CONTROLLER_URL=https://controller.aifabrix.ai

# Optional: CORS – comma-separated allowed origins (e.g. frontend URLs)
# If set, requests with Origin/Referer not in this list get 403
MISO_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:*
```

---

## FastAPI

Copy this into your FastAPI app. The client is initialized at startup and the single route returns token + config.

```python
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from miso_client import (
    MisoClient,
    load_config,
    create_fastapi_client_token_endpoint,
)

miso_client: Optional[MisoClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global miso_client
    config = load_config()
    miso_client = MisoClient(config)
    await miso_client.initialize()
    yield
    if miso_client:
        await miso_client.close()


app = FastAPI(lifespan=lifespan)


@app.post("/api/v1/auth/client-token")
async def client_token(request: Request):
    """Returns client token + DataClient config. Origin validated if MISO_ALLOWED_ORIGINS is set."""
    handler = create_fastapi_client_token_endpoint(miso_client)
    return await handler(request)
```

Run: `uvicorn your_module:app --reload`

---

## Flask

Copy this into your Flask app. The client is initialized on first request.

```python
import asyncio
from flask import Flask
from miso_client import (
    MisoClient,
    load_config,
    create_flask_client_token_endpoint,
)

app = Flask(__name__)


def get_miso_client() -> MisoClient:
    if not hasattr(get_miso_client, "_client"):
        config = load_config()
        client = MisoClient(config)
        asyncio.run(client.initialize())
        get_miso_client._client = client
    return get_miso_client._client


@app.post("/api/v1/auth/client-token")
def client_token():
    """Returns client token + DataClient config. Origin validated if MISO_ALLOWED_ORIGINS is set."""
    client = get_miso_client()
    handler = create_flask_client_token_endpoint(client)
    data, status_code = handler()
    return data, status_code
```

Run: `flask run` or `python -m flask run`

---

## Response shape

Success (200):

```json
{
  "token": "eyJ...",
  "expiresIn": 1800,
  "config": {
    "baseUrl": "http://localhost:8000",
    "controllerUrl": "https://controller.aifabrix.ai",
    "controllerPublicUrl": "https://controller.aifabrix.ai",
    "clientId": "your-client-id",
    "clientTokenUri": "/api/v1/auth/client-token"
  }
}
```

Errors:

- **403** – Origin validation failed (when `MISO_ALLOWED_ORIGINS` is set and request origin is not allowed).
- **503** – MisoClient not initialized.
- **500** – Controller error or misconfiguration.

---

## Using the token in the frontend

`POST` your backend route (e.g. `POST /api/v1/auth/client-token`). The browser sends the `Origin` header automatically. Use the returned `token` and `config.controllerUrl` (or `controllerPublicUrl`) to call the Miso Controller from the client (e.g. with the JavaScript/TypeScript SDK or fetch).

---

## Optional: config in code

If you prefer not to use env vars for config:

```python
from miso_client import MisoClient, create_fastapi_client_token_endpoint
from miso_client.models.config import MisoClientConfig

config = MisoClientConfig(
    controller_url="https://controller.aifabrix.ai",
    client_id="my-app",
    client_secret="secret",
    allowedOrigins=[
        "http://localhost:3000",
        "http://localhost:*",
    ],
)
client = MisoClient(config)
# Then await client.initialize() in your startup/lifespan
```

Use this `client` when creating the endpoint: `create_fastapi_client_token_endpoint(client)` or `create_flask_client_token_endpoint(client)`.
