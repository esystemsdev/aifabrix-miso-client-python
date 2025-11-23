"""
Authentication strategy handler utility.

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
        """
        Build authentication headers for a specific auth method.

        Args:
            method: Authentication method to use
            strategy: Auth strategy configuration
            client_token: Optional client token (for client-token and client-credentials methods)

        Returns:
            Dictionary of headers to add to the request

        Raises:
            ValueError: If required credentials are missing for the method
        """
        headers: Dict[str, str] = {}

        if method == "bearer":
            if not strategy.bearerToken:
                raise ValueError("bearerToken is required for bearer authentication method")
            headers["Authorization"] = f"Bearer {strategy.bearerToken}"

        elif method == "client-token":
            if not client_token:
                raise ValueError("client_token is required for client-token authentication method")
            headers["x-client-token"] = client_token

        elif method == "client-credentials":
            # Client credentials uses the same client token mechanism
            # The client token is already automatically sent via _ensure_client_token
            # This method is mainly for strategy ordering
            if not client_token:
                raise ValueError(
                    "client_token is required for client-credentials authentication method"
                )
            headers["x-client-token"] = client_token

        elif method == "api-key":
            if not strategy.apiKey:
                raise ValueError("apiKey is required for api-key authentication method")
            # API key is sent as Bearer token (same format as bearer tokens)
            headers["Authorization"] = f"Bearer {strategy.apiKey}"

        return headers

    @staticmethod
    def should_try_method(method: AuthMethod, strategy: AuthStrategy) -> bool:
        """
        Check if a method should be tried based on the strategy.

        Args:
            method: Authentication method to check
            strategy: Auth strategy configuration

        Returns:
            True if method should be tried, False otherwise
        """
        return method in strategy.methods

    @staticmethod
    def get_default_strategy() -> AuthStrategy:
        """
        Get default authentication strategy.

        Returns:
            Default AuthStrategy with ['bearer', 'client-token'] methods
        """
        return AuthStrategy(methods=["bearer", "client-token"])
