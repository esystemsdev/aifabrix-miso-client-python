"""
Roles API implementation.

Provides typed interfaces for roles endpoints.
"""

from typing import Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient
from .types.roles_types import GetRolesResponse, RefreshRolesResponse


class RolesApi:
    """Roles API client for role endpoints."""

    # Endpoint constants
    ROLES_ENDPOINT = "/api/v1/auth/roles"
    ROLES_REFRESH_ENDPOINT = "/api/v1/auth/roles/refresh"

    def __init__(self, http_client: HttpClient):
        """
        Initialize Roles API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client

    async def get_roles(
        self,
        token: Optional[str] = None,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> GetRolesResponse:
        """
        Get user roles (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            environment: Optional environment key filter
            application: Optional application key filter
            auth_strategy: Optional authentication strategy

        Returns:
            GetRolesResponse with user roles

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
                "GET", self.ROLES_ENDPOINT, token, params=params, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.ROLES_ENDPOINT, params=params)
        return GetRolesResponse(**response)

    async def refresh_roles(
        self, token: Optional[str] = None, auth_strategy: Optional[AuthStrategy] = None
    ) -> RefreshRolesResponse:
        """
        Refresh user roles (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            auth_strategy: Optional authentication strategy

        Returns:
            RefreshRolesResponse with refreshed roles

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.ROLES_REFRESH_ENDPOINT, token, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.ROLES_REFRESH_ENDPOINT)
        return RefreshRolesResponse(**response)
