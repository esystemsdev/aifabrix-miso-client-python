"""Server-side bootstrap contracts; client credentials never enter the snapshot."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ..errors import MisoClientError

InvalidationReason = Literal["authorization-denied", "snapshot-expired", "protocol-error", "closed"]
ChangeHandler = Callable[[Tuple[str, ...]], None]
InvalidationHandler = Callable[[InvalidationReason], None]


SAFE_ERROR_CODES = frozenset(
    {
        "authorization-denied",
        "snapshot-expired",
        "protocol-error",
        "closed",
        "temporarily-unavailable",
        "transport-error",
        "invalid-auth-mode",
        "invalid-bootstrap-settings",
        "invalid-bootstrap-http-client",
        "initialization-failed",
        "required-secret-unavailable",
        "not-initialized",
        "token-unavailable",
        "token-expired",
        "cleanup-failed",
        "untrusted-request-target",
        "operation-failed",
    }
)


class BootstrapError(MisoClientError):
    """Safe bootstrap failure with a fixed category and no transport payload."""

    def __init__(self, code: str, status_code: Optional[int] = None):
        code = code if code in SAFE_ERROR_CODES else "operation-failed"
        super().__init__("Secret runtime operation failed: " + code, status_code=status_code)
        self.code = code


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
