"""Application context service for extracting application, applicationId, and environment.

This service provides a unified way to extract application context information
from client tokens and clientId format with consistent fallback logic.
"""

import asyncio
from typing import Dict, Optional

from ..utils.internal_http_client import InternalHttpClient
from ..utils.token_utils import extract_client_token_info


class ApplicationContext:
    """Application context data structure."""

    def __init__(
        self,
        application: str,
        application_id: Optional[str] = None,
        environment: str = "unknown",
    ):
        """Initialize application context.

        Args:
            application: Application name
            application_id: Application ID (optional)
            environment: Environment name

        """
        self.application = application
        self.application_id = application_id
        self.environment = environment

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Convert to dictionary.

        Returns:
            Dictionary with application, applicationId, and environment

        """
        return {
            "application": self.application,
            "applicationId": self.application_id,
            "environment": self.environment,
        }


class ApplicationContextService:
    """Service for extracting application context with consistent fallback logic.

    Extracts application, applicationId, and environment from:
    1. Client token (if available)
    2. ClientId format parsing: `miso-controller-{environment}-{application}`
    3. Defaults to clientId as application name

    Supports overwriting values for dataplane use cases where external
    applications need logging on their behalf.
    """

    def __init__(self, internal_http_client: InternalHttpClient):
        """Initialize application context service.

        Args:
            internal_http_client: Internal HTTP client instance (for accessing client token)

        """
        self.config = internal_http_client.config
        self.internal_http_client = internal_http_client
        self._cached_context: Optional[ApplicationContext] = None

    def _parse_client_id_format(self, client_id: str) -> Dict[str, Optional[str]]:
        """Parse clientId format: `miso-controller-{environment}-{application}`.

        Args:
            client_id: Client ID string

        Returns:
            Dictionary with application and environment (or None if format doesn't match)

        """
        if not client_id or not isinstance(client_id, str):
            return {"application": None, "environment": None}

        # Parse format: miso-controller-{environment}-{application}
        parts = client_id.split("-")
        if len(parts) < 4 or parts[0] != "miso" or parts[1] != "controller":
            # Format doesn't match, return None
            return {"application": None, "environment": None}

        # Extract environment (index 2)
        environment = parts[2] if len(parts) > 2 else None

        # Extract application (remaining parts joined with -)
        application = "-".join(parts[3:]) if len(parts) > 3 else None

        return {
            "application": application,
            "environment": environment,
        }

    def _cache_context(self, context: ApplicationContext) -> ApplicationContext:
        """Persist context in memory cache and return it."""
        self._cached_context = context
        return context

    def _build_default_context(self) -> ApplicationContext:
        """Build default fallback context."""
        return ApplicationContext(
            application=self.config.client_id,
            application_id=None,
            environment="unknown",
        )

    def _build_context_from_parsed_client_id(self) -> ApplicationContext:
        """Build context using clientId naming convention fallback."""
        parsed = self._parse_client_id_format(self.config.client_id)
        application = parsed.get("application")
        environment = parsed.get("environment")
        if application and environment:
            return ApplicationContext(
                application=application,
                application_id=None,
                environment=environment,
            )
        return self._build_default_context()

    def _build_context_from_token_info(
        self, token_info: Dict[str, Optional[str]]
    ) -> ApplicationContext:
        """Build context from extracted client token claims."""
        return ApplicationContext(
            application=token_info.get("application") or self.config.client_id,
            application_id=token_info.get("applicationId"),
            environment=token_info.get("environment") or "unknown",
        )

    def _try_context_from_cached_token_sync(self) -> Optional[ApplicationContext]:
        """Try extracting context from currently cached client token only."""
        client_token = self.internal_http_client.token_manager.client_token
        if not client_token:
            return None
        try:
            token_info = extract_client_token_info(client_token)
        except Exception:
            return None
        if not (token_info.get("application") or token_info.get("environment")):
            return None
        return self._build_context_from_token_info(token_info)

    async def _try_context_from_client_token_async(self) -> Optional[ApplicationContext]:
        """Try extracting context from fetched client token."""
        try:
            client_token = await self.internal_http_client.token_manager.get_client_token()
        except (RuntimeError, asyncio.CancelledError, ConnectionError):
            return ApplicationContext(
                application="unknown", application_id=None, environment="unknown"
            )
        except Exception:
            return None

        try:
            token_info = extract_client_token_info(client_token)
        except Exception:
            return None
        if not (token_info.get("application") or token_info.get("environment")):
            return None
        return self._build_context_from_token_info(token_info)

    @staticmethod
    def _has_overwrites(
        overwrite_application: Optional[str],
        overwrite_application_id: Optional[str],
        overwrite_environment: Optional[str],
    ) -> bool:
        """Return True when at least one overwrite is provided."""
        return (
            overwrite_application is not None
            or overwrite_application_id is not None
            or overwrite_environment is not None
        )

    async def _resolve_uncached_context(self) -> ApplicationContext:
        """Resolve context using token, then clientId fallback."""
        token_context = await self._try_context_from_client_token_async()
        return (
            token_context
            if token_context is not None
            else self._build_context_from_parsed_client_id()
        )

    def get_application_context_sync(self) -> ApplicationContext:
        """Get application context synchronously (no controller calls).

        Uses cached client token or parses clientId format.
        Matches TypeScript getApplicationContext() behavior.

        Returns:
            ApplicationContext object with application, applicationId, and environment

        """
        # Use cached context if available
        if self._cached_context is not None:
            return self._cached_context

        token_context = self._try_context_from_cached_token_sync()
        if token_context is not None:
            return self._cache_context(token_context)
        return self._cache_context(self._build_context_from_parsed_client_id())

    async def get_application_context(
        self,
        overwrite_application: Optional[str] = None,
        overwrite_application_id: Optional[str] = None,
        overwrite_environment: Optional[str] = None,
    ) -> ApplicationContext:
        """Get application context with optional overwrite values."""
        if self._has_overwrites(
            overwrite_application, overwrite_application_id, overwrite_environment
        ):
            return self._build_context_with_overwrites(
                overwrite_application, overwrite_application_id, overwrite_environment
            )

        if self._cached_context is not None:
            return self._cached_context

        return self._cache_context(await self._resolve_uncached_context())

    def _build_context_with_overwrites(
        self,
        overwrite_application: Optional[str],
        overwrite_application_id: Optional[str],
        overwrite_environment: Optional[str],
    ) -> ApplicationContext:
        """Build context with overwrite values plus fallback defaults."""
        base_context = self._resolve_base_context_for_overwrites()
        application = self._pick_overwrite_str(overwrite_application, base_context.application)
        application_id = self._pick_overwrite(overwrite_application_id, base_context.application_id)
        environment = self._pick_overwrite_str(overwrite_environment, base_context.environment)
        return ApplicationContext(
            application=application,
            application_id=application_id,
            environment=environment,
        )

    def _resolve_base_context_for_overwrites(self) -> ApplicationContext:
        """Resolve base context used when applying overwrite values."""
        if self._cached_context is not None:
            return self._cached_context
        try:
            return self._build_context_from_parsed_client_id()
        except Exception:
            return self._build_default_context()

    @staticmethod
    def _pick_overwrite(value: Optional[str], fallback: Optional[str]) -> Optional[str]:
        """Pick overwrite value when provided, otherwise fallback."""
        return value if value is not None else fallback

    @staticmethod
    def _pick_overwrite_str(value: Optional[str], fallback: str) -> str:
        """Pick overwrite value for required string fields."""
        return value if value is not None else fallback

    def clear_cache(self) -> None:
        """Clear cached application context."""
        self._cached_context = None
