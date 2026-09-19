"""Lazy official managed-identity adapter; never a developer credential chain."""

from __future__ import annotations

import importlib
import sys
from typing import Optional, Protocol, cast

from pydantic import SecretStr

from ..models.bootstrap import BootstrapError, IdentityToken


class _AzureToken(Protocol):
    token: str
    expires_on: int


class _Credential(Protocol):
    async def get_token(self, scope: str) -> _AzureToken: ...
    async def close(self) -> None: ...


class AzureIdentityProvider:
    """Owned adapter for azure.identity.aio.ManagedIdentityCredential."""

    def __init__(self, client_id: Optional[str] = None):
        if sys.version_info < (3, 9):
            raise BootstrapError("azure-requires-python-3.9")
        credential: Optional[_Credential] = None
        try:
            module = importlib.import_module("azure.identity.aio")
            credential = cast(
                _Credential,
                module.ManagedIdentityCredential(
                    client_id=client_id, retry_total=0, logging_enable=False
                ),
            )
        except Exception:
            pass
        if credential is None:
            raise BootstrapError("azure-extra-unavailable")
        self._credential = credential

    async def get_token(self, scope: str) -> IdentityToken:
        """Acquire one managed-identity token; transport sanitizes adapter errors."""
        result = await self._credential.get_token(scope)
        return IdentityToken(token=SecretStr(result.token), expires_at=result.expires_on)

    async def close(self) -> None:
        """Close only the credential owned by this adapter."""
        await self._credential.close()
