"""
Authentication service for token validation and user management.

This module handles authentication operations including client token management,
token validation, user information retrieval, and logout functionality.
"""

from typing import Optional
from ..models.config import UserInfo, AuthResult
from ..services.redis import RedisService
from ..utils.http_client import HttpClient


class AuthService:
    """Authentication service for token validation and user management."""
    
    def __init__(self, http_client: HttpClient, redis: RedisService):
        """
        Initialize authentication service.
        
        Args:
            http_client: HTTP client instance
            redis: Redis service instance
        """
        self.config = http_client.config
        self.http_client = http_client
        self.redis = redis
    
    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.
        
        This is called automatically by HttpClient, but can be called manually if needed.
        
        Returns:
            Client token string
            
        Raises:
            AuthenticationError: If token fetch fails
        """
        return await self.http_client.get_environment_token()
    
    def login(self, redirect_uri: str) -> str:
        """
        Initiate login flow by redirecting to controller.
        
        Returns the login URL for browser redirect or manual navigation.
        Backend will extract environment and application from client token.
        
        Args:
            redirect_uri: URI to redirect to after successful login
            
        Returns:
            Login URL string
        """
        return f"{self.config.controller_url}/api/auth/login?redirect={redirect_uri}"
    
    async def validate_token(self, token: str) -> bool:
        """
        Validate token with controller.
        
        Args:
            token: JWT token to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            result = await self.http_client.authenticated_request(
                "POST",
                "/api/auth/validate",  # Backend knows app/env from client token
                token
            )
            
            auth_result = AuthResult(**result)
            return auth_result.authenticated
            
        except Exception:
            # Token validation failed, return false
            return False
    
    async def get_user(self, token: str) -> Optional[UserInfo]:
        """
        Get user information from token.
        
        Args:
            token: JWT token
            
        Returns:
            UserInfo if token is valid, None otherwise
        """
        try:
            result = await self.http_client.authenticated_request(
                "POST",
                "/api/auth/validate",
                token
            )
            
            auth_result = AuthResult(**result)
            
            if auth_result.authenticated and auth_result.user:
                return auth_result.user
            
            return None
            
        except Exception:
            # Failed to get user info, return null
            return None
    
    async def get_user_info(self, token: str) -> Optional[UserInfo]:
        """
        Get user information from GET /api/auth/user endpoint.
        
        Args:
            token: JWT token
            
        Returns:
            UserInfo if token is valid, None otherwise
        """
        try:
            user_data = await self.http_client.authenticated_request(
                "GET",
                "/api/auth/user",
                token
            )
            
            return UserInfo(**user_data)
            
        except Exception:
            # Failed to get user info, return None
            return None
    
    async def logout(self) -> None:
        """
        Logout user.
        
        Backend extracts app/env from client token (no body needed).
        
        Raises:
            MisoClientError: If logout fails
        """
        try:
            # Backend extracts app/env from client token
            await self.http_client.request("POST", "/api/auth/logout")
        except Exception as e:
            # Logout failed, re-raise error for application to handle
            from ..errors import MisoClientError
            raise MisoClientError(f"Logout failed: {str(e)}")
    
    async def is_authenticated(self, token: str) -> bool:
        """
        Check if user is authenticated (has valid token).
        
        Args:
            token: JWT token
            
        Returns:
            True if user is authenticated, False otherwise
        """
        return await self.validate_token(token)
