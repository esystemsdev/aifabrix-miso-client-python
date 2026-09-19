"""Server-side bootstrap contracts; no Azure dependency is imported here."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Literal, Optional, Protocol, Tuple

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..errors import MisoClientError

InvalidationReason = Literal["authorization-denied", "snapshot-expired", "protocol-error", "closed"]
ChangeHandler = Callable[[Tuple[str, ...]], None]
InvalidationHandler = Callable[[InvalidationReason], None]


class BootstrapError(MisoClientError):
    """Safe bootstrap failure with a fixed category and no transport payload."""

    def __init__(self, code: str, status_code: Optional[int] = None):
        super().__init__("Secret runtime operation failed: " + code, status_code=status_code)
        self.code = code


class IdentityToken(BaseModel):
    """In-memory identity token returned by an injected async provider."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)
    token: SecretStr = Field(repr=False, exclude=True)
    expires_at: float


class IdentityTokenProvider(Protocol):
    """Optional test/host identity seam; ownership remains with the caller."""

    async def get_token(self, scope: str) -> IdentityToken:
        """Acquire an Entra token for one scope."""
        ...


class ApplicationTokenProvider(ABC):
    """Private-state application authentication alternative to a client secret."""

    @abstractmethod
    async def get_token(self) -> str:
        """Return a currently usable application token or fail closed."""

    @abstractmethod
    def invalidate(self, reason: InvalidationReason) -> None:
        """Invalidate token and secret access synchronously."""

    @abstractmethod
    async def handle_auth_error(self, code: str, token: Optional[str]) -> None:
        """Handle an allowlisted controller code for the token used by a request."""


class BootstrapContext(BaseModel):
    """Immutable context supplied exclusively by the controller."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    installationId: str = Field(min_length=1, max_length=128)
    applicationId: str = Field(min_length=1, max_length=128)
    environmentId: str = Field(min_length=1, max_length=128)
