"""SDK exceptions and error handling.

This module defines custom exceptions for the MisoClient SDK.
"""

from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from .models.error_response import ErrorResponse

# Authentication method type for error tracking (aligned with config.py and error_response.py)
AuthMethod = Literal["bearer", "client-token", "client-credentials", "api-key"]

# Error codes for encryption operations (aligned with TypeScript SDK)
EncryptionErrorCode = Literal[
    "ENCRYPTION_FAILED",
    "DECRYPTION_FAILED",
    "INVALID_PARAMETER_NAME",
    "ACCESS_DENIED",
    "PARAMETER_NOT_FOUND",
    "ENCRYPTION_KEY_REQUIRED",
]


class MisoClientError(Exception):
    """Base exception for MisoClient SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_body: dict | None = None,
        error_response: "ErrorResponse | None" = None,
        auth_method: Optional[AuthMethod] = None,
    ):
        """Initialize MisoClient error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            error_body: Sanitized error response body (secrets masked)
            error_response: Structured error response object (RFC 7807-style)
            auth_method: Authentication method that failed (for 401 errors)

        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_body = error_body if error_body is not None else None
        self.error_response = error_response

        # Set auth_method from parameter or extract from error_response
        self.auth_method: Optional[AuthMethod] = auth_method
        if self.auth_method is None and error_response is not None:
            self.auth_method = error_response.authMethod

        # Enhance message with structured error information if available
        if error_response and error_response.errors:
            if len(error_response.errors) == 1:
                self.message = error_response.errors[0]
            else:
                self.message = f"{error_response.title}: {'; '.join(error_response.errors)}"
            # Override status_code from structured response if available
            if error_response.statusCode:
                self.status_code = error_response.statusCode


class AuthenticationError(MisoClientError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(MisoClientError):
    """Raised when authorization check fails."""

    pass


class ConnectionError(MisoClientError):
    """Raised when connection to controller or Redis fails."""

    pass


class ConfigurationError(MisoClientError):
    """Raised when configuration is invalid."""

    pass


class EncryptionError(MisoClientError):
    """Raised when encryption/decryption operations fail."""

    def __init__(
        self,
        message: str,
        code: Optional[EncryptionErrorCode] = None,
        parameter_name: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        """Initialize encryption error.

        Args:
            message: Error message
            code: Error code for programmatic handling
            parameter_name: The parameter name that caused the error
            status_code: HTTP status code if applicable

        """
        super().__init__(message, status_code=status_code)
        self.code = code
        self.parameter_name = parameter_name
