"""Authentication strategy handler utility.

This module provides utilities for managing authentication strategies with
priority-based fallback support.
"""

from typing import Dict, Optional

from ..models.config import AuthMethod, AuthStrategy


class AuthStrategyHandler:
    """Handler for authentication strategies with priority-based fallback."""

    @staticmethod
    def build_auth_headers(
        method: AuthMethod,
        strategy: AuthStrategy,
        client_token: Optional[str] = None,
    ) -> Dict[str, str]:
        """Build authentication headers for a specific auth method."""
        if method == "bearer":
            return AuthStrategyHandler._bearer_headers(strategy)
        if method in ["client-token", "client-credentials"]:
            return AuthStrategyHandler._client_token_headers(client_token, method)
        if method == "api-key":
            return AuthStrategyHandler._api_key_headers(strategy)
        return {}

    @staticmethod
    def _bearer_headers(strategy: AuthStrategy) -> Dict[str, str]:
        """Build headers for bearer authentication."""
        if not strategy.bearerToken:
            raise ValueError("bearerToken is required for bearer authentication method")
        return {"Authorization": f"Bearer {strategy.bearerToken}"}

    @staticmethod
    def _client_token_headers(client_token: Optional[str], method: AuthMethod) -> Dict[str, str]:
        """Build headers for client token-based authentication methods."""
        if not client_token:
            raise ValueError(f"client_token is required for {method} authentication method")
        return {"x-client-token": client_token}

    @staticmethod
    def _api_key_headers(strategy: AuthStrategy) -> Dict[str, str]:
        """Build headers for API key authentication."""
        if not strategy.apiKey:
            raise ValueError("apiKey is required for api-key authentication method")
        return {"Authorization": f"Bearer {strategy.apiKey}"}

    @staticmethod
    def should_try_method(method: AuthMethod, strategy: AuthStrategy) -> bool:
        """Check if a method should be tried based on the strategy.

        Args:
            method: Authentication method to check
            strategy: Auth strategy configuration

        Returns:
            True if method should be tried, False otherwise

        """
        return method in strategy.methods

    @staticmethod
    def get_default_strategy() -> AuthStrategy:
        """Get default authentication strategy.

        Returns:
            Default AuthStrategy with ['bearer', 'client-token'] methods

        """
        return AuthStrategy(methods=["bearer", "client-token"])
