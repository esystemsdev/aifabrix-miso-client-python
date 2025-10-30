"""
HTTP client utility for controller communication.

This module provides an async HTTP client wrapper that handles communication
with the Miso Controller, including automatic client token management,
retry logic, and error handling.
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Literal
from ..models.config import MisoClientConfig, ClientTokenResponse
from ..errors import MisoClientError, AuthenticationError, ConnectionError


class HttpClient:
    """HTTP client for Miso Controller communication with automatic client token management."""
    
    def __init__(self, config: MisoClientConfig):
        """
        Initialize HTTP client with configuration.
        
        Args:
            config: MisoClient configuration
        """
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self.client_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.token_refresh_lock = asyncio.Lock()
        
    async def _initialize_client(self):
        """Initialize HTTP client if not already initialized."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.config.controller_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                }
            )
    
    async def _get_client_token(self) -> str:
        """
        Get client token, fetching if needed.
        
        Proactively refreshes if token will expire within 60 seconds.
        
        Returns:
            Client token string
            
        Raises:
            AuthenticationError: If token fetch fails
        """
        await self._initialize_client()
        
        now = datetime.now()
        
        # If token exists and not expired (with 60s buffer for proactive refresh), return it
        if (
            self.client_token and 
            self.token_expires_at and 
            self.token_expires_at > now + timedelta(seconds=60)
        ):
            assert self.client_token is not None
            return self.client_token
        
        # Acquire lock to prevent concurrent token fetches
        async with self.token_refresh_lock:
            # Double-check after acquiring lock
            if (
                self.client_token and 
                self.token_expires_at and 
                self.token_expires_at > now + timedelta(seconds=60)
            ):
                assert self.client_token is not None
                return self.client_token
            
            # Fetch new token
            await self._fetch_client_token()
            assert self.client_token is not None
            return self.client_token
    
    async def _fetch_client_token(self) -> None:
        """
        Fetch client token from controller.
        
        Raises:
            AuthenticationError: If token fetch fails
        """
        await self._initialize_client()
        
        try:
            # Use a temporary client to avoid interceptor recursion
            temp_client = httpx.AsyncClient(
                base_url=self.config.controller_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "x-client-id": self.config.client_id,
                    "x-client-secret": self.config.client_secret,
                }
            )
            
            response = await temp_client.post("/api/auth/token")
            await temp_client.aclose()
            
            if response.status_code != 200:
                raise AuthenticationError(
                    f"Failed to get client token: HTTP {response.status_code}",
                    status_code=response.status_code
                )
            
            data = response.json()
            token_response = ClientTokenResponse(**data)
            
            if not token_response.success or not token_response.token:
                raise AuthenticationError("Failed to get client token: Invalid response")
            
            self.client_token = token_response.token
            # Set expiration with 30 second buffer before actual expiration
            expires_in = max(0, token_response.expiresIn - 30)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
        except httpx.HTTPError as e:
            raise ConnectionError(f"Failed to get client token: {str(e)}")
        except Exception as e:
            if isinstance(e, (AuthenticationError, ConnectionError)):
                raise
            raise AuthenticationError(f"Failed to get client token: {str(e)}")
    
    async def _ensure_client_token(self):
        """Ensure client token is set in headers."""
        token = await self._get_client_token()
        if self.client:
            self.client.headers["x-client-token"] = token
    
    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def get(self, url: str, **kwargs) -> Any:
        """
        Make GET request.
        
        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response data (JSON parsed)
            
        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.get(url, **kwargs)
            
            # Handle 401 - clear token to force refresh
            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")
    
    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Make POST request.
        
        Args:
            url: Request URL
            data: Request data (will be JSON encoded)
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response data (JSON parsed)
            
        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.post(url, json=data, **kwargs)
            
            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")
    
    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Make PUT request.
        
        Args:
            url: Request URL
            data: Request data (will be JSON encoded)
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response data (JSON parsed)
            
        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.put(url, json=data, **kwargs)
            
            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")
    
    async def delete(self, url: str, **kwargs) -> Any:
        """
        Make DELETE request.
        
        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response data (JSON parsed)
            
        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.delete(url, **kwargs)
            
            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {}
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")
    
    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Generic request method.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data (for POST/PUT)
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response data (JSON parsed)
            
        Raises:
            MisoClientError: If request fails
        """
        method_upper = method.upper()
        if method_upper == "GET":
            return await self.get(url, **kwargs)
        elif method_upper == "POST":
            return await self.post(url, data, **kwargs)
        elif method_upper == "PUT":
            return await self.put(url, data, **kwargs)
        elif method_upper == "DELETE":
            return await self.delete(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    
    async def authenticated_request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        token: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Make authenticated request with Bearer token.
        
        IMPORTANT: Client token is sent as x-client-token header (via _ensure_client_token)
        User token is sent as Authorization: Bearer header (this method parameter)
        These are two separate tokens for different purposes.
        
        Args:
            method: HTTP method
            url: Request URL
            token: User authentication token (sent as Bearer token)
            data: Request data (for POST/PUT)
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response data (JSON parsed)
            
        Raises:
            MisoClientError: If request fails
        """
        await self._ensure_client_token()
        
        # Add Bearer token for user authentication
        # x-client-token is automatically added by _ensure_client_token
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers
        
        return await self.request(method, url, data, **kwargs)
    
    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.
        
        This is called automatically by HttpClient but can be called manually.
        
        Returns:
            Client token string
        """
        return await self._get_client_token()
