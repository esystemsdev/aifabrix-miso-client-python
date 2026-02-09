"""Centralized API layer with typed interfaces.

Provides typed interfaces for all controller API calls, organized by domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..utils.http_client import HttpClient


class ApiClient:
    """Centralized API client for Miso Controller communication.

    Wraps HttpClient and provides typed interfaces organized by domain.
    """

    def __init__(self, http_client: HttpClient):
        """Initialize API client.

        Args:
            http_client: HttpClient instance

        """
        from .applications_api import ApplicationsApi
        from .auth_api import AuthApi
        from .logs_api import LogsApi
        from .permissions_api import PermissionsApi
        from .roles_api import RolesApi

        self.http_client = http_client
        self.auth = AuthApi(http_client)
        self.roles = RolesApi(http_client)
        self.permissions = PermissionsApi(http_client)
        self.logs = LogsApi(http_client)
        self.applications = ApplicationsApi(http_client)


def __getattr__(name: str):
    """Lazy import of API classes to avoid circular import with HttpClient."""
    if name == "ApplicationsApi":
        from .applications_api import ApplicationsApi

        return ApplicationsApi
    if name == "AuthApi":
        from .auth_api import AuthApi

        return AuthApi
    if name == "LogsApi":
        from .logs_api import LogsApi

        return LogsApi
    if name == "PermissionsApi":
        from .permissions_api import PermissionsApi

        return PermissionsApi
    if name == "RolesApi":
        from .roles_api import RolesApi

        return RolesApi
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ApiClient", "ApplicationsApi", "AuthApi", "LogsApi", "PermissionsApi", "RolesApi"]
