"""Applications API implementation.

Provides typed interfaces for application status endpoints:
- Update self status (POST /api/v1/environments/{envKey}/applications/self/status)
- Get application status (GET /api/v1/environments/{envKey}/applications/{appKey}/status)
"""

from typing import Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient
from .response_utils import normalize_api_response
from .types.applications_types import (
    ApplicationStatusResponse,
    UpdateSelfStatusRequest,
    UpdateSelfStatusResponse,
)


class ApplicationsApi:
    """Applications API client for application status endpoints."""

    SELF_STATUS_ENDPOINT = "/api/v1/environments/{env_key}/applications/self/status"
    APPLICATION_STATUS_ENDPOINT = "/api/v1/environments/{env_key}/applications/{app_key}/status"

    def __init__(self, http_client: HttpClient):
        """Initialize Applications API client.

        Args:
            http_client: HttpClient instance

        """
        self.http_client = http_client

    def _build_url(self, template: str, env_key: str, app_key: Optional[str] = None) -> str:
        """Build URL by replacing path parameters."""
        url = template.replace("{env_key}", env_key)
        if app_key is not None:
            url = url.replace("{app_key}", app_key)
        return url

    def _should_use_bearer(self, auth_strategy: Optional[AuthStrategy]) -> bool:
        """Check if auth_strategy has bearer token for authenticated_request."""
        if not auth_strategy:
            return False
        if "bearer" not in (auth_strategy.methods or []):
            return False
        return bool(auth_strategy.bearerToken)

    async def update_self_status(
        self,
        env_key: str,
        body: UpdateSelfStatusRequest,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> UpdateSelfStatusResponse:
        """Update own application status and URLs (POST self/status).

        Uses client credentials when auth_strategy is None.
        Uses bearer token or request_with_auth_strategy when auth_strategy provided.

        Args:
            env_key: Environment key
            body: Update request (status, url, internalUrl, port)
            auth_strategy: Optional authentication strategy

        Returns:
            UpdateSelfStatusResponse with success and application data

        Raises:
            MisoClientError: If request fails

        """
        url = self._build_url(self.SELF_STATUS_ENDPOINT, env_key)
        data = body.model_dump(exclude_none=True)

        if auth_strategy is None:
            response = await self.http_client.post(url, data=data)
        elif self._should_use_bearer(auth_strategy):
            token = auth_strategy.bearerToken or ""
            response = await self.http_client.authenticated_request(
                "POST",
                url,
                token,
                data=data,
                auth_strategy=auth_strategy,
            )
        else:
            response = await self.http_client.request_with_auth_strategy(
                "POST",
                url,
                auth_strategy,
                data=data,
            )

        response = normalize_api_response(response)
        return UpdateSelfStatusResponse(**response)

    async def get_application_status(
        self,
        env_key: str,
        app_key: str,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> ApplicationStatusResponse:
        """Get application status and URLs (GET application status).

        Uses client credentials when auth_strategy is None.
        Uses bearer token or request_with_auth_strategy when auth_strategy provided.

        Args:
            env_key: Environment key
            app_key: Application key
            auth_strategy: Optional authentication strategy

        Returns:
            ApplicationStatusResponse with application metadata (no configuration)

        Raises:
            MisoClientError: If request fails

        """
        url = self._build_url(self.APPLICATION_STATUS_ENDPOINT, env_key, app_key)

        if auth_strategy is None:
            response = await self.http_client.get(url)
        elif self._should_use_bearer(auth_strategy):
            token = auth_strategy.bearerToken or ""
            response = await self.http_client.authenticated_request(
                "GET",
                url,
                token,
                auth_strategy=auth_strategy,
            )
        else:
            response = await self.http_client.request_with_auth_strategy(
                "GET",
                url,
                auth_strategy,
            )

        response = normalize_api_response(response)
        return ApplicationStatusResponse(**response)
