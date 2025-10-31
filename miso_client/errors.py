"""
SDK exceptions and error handling.

This module defines custom exceptions for the MisoClient SDK.
"""


class MisoClientError(Exception):
    """Base exception for MisoClient SDK errors."""

    def __init__(
        self, message: str, status_code: int | None = None, error_body: dict | None = None
    ):
        """
        Initialize MisoClient error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            error_body: Sanitized error response body (secrets masked)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_body = error_body if error_body is not None else None


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
