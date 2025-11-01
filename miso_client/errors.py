"""
SDK exceptions and error handling.

This module defines custom exceptions for the MisoClient SDK.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.error_response import ErrorResponse


class MisoClientError(Exception):
    """Base exception for MisoClient SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_body: dict | None = None,
        error_response: "ErrorResponse | None" = None,
    ):
        """
        Initialize MisoClient error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            error_body: Sanitized error response body (secrets masked)
            error_response: Structured error response object (RFC 7807-style)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_body = error_body if error_body is not None else None
        self.error_response = error_response

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
