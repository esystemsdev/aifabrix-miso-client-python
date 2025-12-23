"""
Permissions API implementation.

Provides typed interfaces for permissions endpoints.
"""

from typing import Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient
from .types.permissions_types import GetPermissionsResponse, RefreshPermissionsResponse


class PermissionsApi:
    """Permissions API client for permission endpoints."""

    # Endpoint constants
    PERMISSIONS_ENDPOINT = "/api/v1/auth/permissions"
    PERMISSIONS_REFRESH_ENDPOINT = "/api/v1/auth/permissions/refresh"

    def __init__(self, http_client: HttpClient):
        """
        Initialize Permissions API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client

    async def get_permissions(
        self,
        token: Optional[str] = None,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> GetPermissionsResponse:
        """
        Get user permissions (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            environment: Optional environment key filter
            application: Optional application key filter
            auth_strategy: Optional authentication strategy

        Returns:
            GetPermissionsResponse with user permissions

        Raises:
            MisoClientError: If request fails
        """
        params = {}
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application

        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.PERMISSIONS_ENDPOINT, token, params=params, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.PERMISSIONS_ENDPOINT, params=params)
        return GetPermissionsResponse(**response)

    async def refresh_permissions(
        self, token: Optional[str] = None, auth_strategy: Optional[AuthStrategy] = None
    ) -> RefreshPermissionsResponse:
        """
        Refresh user permissions (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            auth_strategy: Optional authentication strategy

        Returns:
            RefreshPermissionsResponse with refreshed permissions

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.PERMISSIONS_REFRESH_ENDPOINT, token, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.PERMISSIONS_REFRESH_ENDPOINT)
        return RefreshPermissionsResponse(**response)
