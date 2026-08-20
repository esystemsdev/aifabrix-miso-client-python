"""Authorization mixin providing shared application context functionality.

This mixin provides common methods for role and permission services
to access application context for environment/application detection.
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..services.application_context import ApplicationContextService
    from ..utils.http_client import HttpClient


class ApplicationContextMixin:
    """Mixin providing application context access for authorization services."""

    # Type hints for attributes that must be set by implementing class
    http_client: "HttpClient"
    _app_context_service: Optional["ApplicationContextService"]

    def _get_app_context_service(self) -> "ApplicationContextService":
        """Get or create application context service.

        Returns:
            ApplicationContextService instance (cached after first creation)

        """
        from ..services.application_context import ApplicationContextService

        if self._app_context_service is None:
            internal_client = self.http_client.get_internal_client()
            self._app_context_service = ApplicationContextService(internal_client)
        return self._app_context_service

    def _get_environment_from_context(self) -> Optional[str]:
        """Get environment from application context (synchronous, uses cached value).

        Returns:
            Environment string if found, None otherwise

        """
        try:
            app_context_service = self._get_app_context_service()
            context = app_context_service.get_application_context_sync()
            env = context.environment
            return env if env and env != "unknown" else None
        except Exception:
            return None
