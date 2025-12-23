"""
Centralized API layer with typed interfaces.

Provides typed interfaces for all controller API calls, organized by domain.
"""

from ..utils.http_client import HttpClient
from .auth_api import AuthApi
from .logs_api import LogsApi
from .permissions_api import PermissionsApi
from .roles_api import RolesApi


class ApiClient:
    """
    Centralized API client for Miso Controller communication.

    Wraps HttpClient and provides typed interfaces organized by domain.
    """

    def __init__(self, http_client: HttpClient):
        """
        Initialize API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client
        self.auth = AuthApi(http_client)
        self.roles = RolesApi(http_client)
        self.permissions = PermissionsApi(http_client)
        self.logs = LogsApi(http_client)


__all__ = ["ApiClient", "AuthApi", "RolesApi", "PermissionsApi", "LogsApi"]
