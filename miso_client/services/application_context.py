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

        # Try to get cached client token (synchronous, no fetch)
        client_token = self.internal_http_client.token_manager.client_token

        if client_token:
            try:
                token_info = extract_client_token_info(client_token)

                application = token_info.get("application")
                application_id = token_info.get("applicationId")
                environment = token_info.get("environment")

                # If we got values from token, use them
                if application or environment:
                    context = ApplicationContext(
                        application=application or self.config.client_id,
                        application_id=application_id,
                        environment=environment or "unknown",
                    )
                    self._cached_context = context
                    return context
            except Exception:
                # Token extraction failed, fall back to clientId parsing
                pass

        # Fall back to parsing clientId format
        parsed = self._parse_client_id_format(self.config.client_id)
        application = parsed.get("application")
        environment = parsed.get("environment")

        # If parsing succeeded, use parsed values
        if application and environment:
            context = ApplicationContext(
                application=application,
                application_id=None,
                environment=environment,
            )
            self._cached_context = context
            return context

        # Final fallback: use clientId as application name
        context = ApplicationContext(
            application=self.config.client_id,
            application_id=None,
            environment="unknown",
        )
        self._cached_context = context
        return context

    async def get_application_context(
        self,
        overwrite_application: Optional[str] = None,
        overwrite_application_id: Optional[str] = None,
        overwrite_environment: Optional[str] = None,
    ) -> ApplicationContext:
        """Get application context with optional overwrites.

        Supports overwriting values for dataplane use cases where external
        applications need logging on their behalf.

        Args:
            overwrite_application: Override application name
            overwrite_application_id: Override application ID
            overwrite_environment: Override environment name

        Returns:
            ApplicationContext object with application, applicationId, and environment

        """
        # If overwrites are provided, use them directly (don't cache)
        if (
            overwrite_application is not None
            or overwrite_application_id is not None
            or overwrite_environment is not None
        ):
            return self._build_context_with_overwrites(
                overwrite_application, overwrite_application_id, overwrite_environment
            )

        # Use cached context if available
        if self._cached_context is not None:
            return self._cached_context

        # Extract from client token first
        try:
            # Handle case where HTTP client might be closed during teardown
            try:
                client_token = await self.internal_http_client.token_manager.get_client_token()
            except (RuntimeError, asyncio.CancelledError, ConnectionError):
                # Event loop closed or connection error - return default context
                return ApplicationContext(
                    application="unknown", application_id=None, environment="unknown"
                )
            token_info = extract_client_token_info(client_token)

            application = token_info.get("application")
            application_id = token_info.get("applicationId")
            environment = token_info.get("environment")

            # If we got values from token, use them
            if application or environment:
                context = ApplicationContext(
                    application=application or self.config.client_id,
                    application_id=application_id,
                    environment=environment or "unknown",
                )
                self._cached_context = context
                return context
        except Exception:
            # Token extraction failed, fall back to clientId parsing
            pass

        # Fall back to parsing clientId format
        parsed = self._parse_client_id_format(self.config.client_id)
        application = parsed.get("application")
        environment = parsed.get("environment")

        # If parsing succeeded, use parsed values
        if application and environment:
            context = ApplicationContext(
                application=application,
                application_id=None,
                environment=environment,
            )
            self._cached_context = context
            return context

        # Final fallback: use clientId as application name
        context = ApplicationContext(
            application=self.config.client_id,
            application_id=None,
            environment="unknown",
        )
        self._cached_context = context
        return context

    def _build_context_with_overwrites(
        self,
        overwrite_application: Optional[str],
        overwrite_application_id: Optional[str],
        overwrite_environment: Optional[str],
    ) -> ApplicationContext:
        """Build context with overwrites, falling back to defaults for non-overwritten values.

        Args:
            overwrite_application: Override application name
            overwrite_application_id: Override application ID
            overwrite_environment: Override environment name

        Returns:
            ApplicationContext with overwrites applied

        """
        # Get base context for non-overwritten values
        base_context = self._cached_context
        if base_context is None:
            # Try to get context synchronously (without async call)
            # This is a fallback for when cache is not available
            try:
                # Parse clientId format as fallback
                parsed = self._parse_client_id_format(self.config.client_id)
                base_context = ApplicationContext(
                    application=parsed.get("application") or self.config.client_id,
                    application_id=None,
                    environment=parsed.get("environment") or "unknown",
                )
            except Exception:
                base_context = ApplicationContext(
                    application=self.config.client_id,
                    application_id=None,
                    environment="unknown",
                )

        return ApplicationContext(
            application=(
                overwrite_application
                if overwrite_application is not None
                else base_context.application
            ),
            application_id=(
                overwrite_application_id
                if overwrite_application_id is not None
                else base_context.application_id
            ),
            environment=(
                overwrite_environment
                if overwrite_environment is not None
                else base_context.environment
            ),
        )

    def clear_cache(self) -> None:
        """Clear cached application context."""
        self._cached_context = None
