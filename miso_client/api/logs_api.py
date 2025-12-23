"""
Logs API implementation.

Provides typed interfaces for logging endpoints.
"""

from typing import Optional

from ..models.config import LogEntry
from ..utils.http_client import HttpClient
from .types.logs_types import BatchLogRequest, BatchLogResponse, LogRequest, LogResponse


class LogsApi:
    """Logs API client for logging endpoints."""

    # Endpoint constants
    LOGS_ENDPOINT = "/api/v1/logs"
    LOGS_BATCH_ENDPOINT = "/api/v1/logs/batch"

    def __init__(self, http_client: HttpClient):
        """
        Initialize Logs API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client

    async def send_log(self, log_entry: LogRequest, token: Optional[str] = None) -> LogResponse:
        """
        Send log entry (POST).

        Supports Bearer token, x-client-token, or client credentials authentication.
        If token is provided, uses authenticated_request. Otherwise uses client credentials (automatic).

        Args:
            log_entry: LogRequest with type and data
            token: Optional user token (if not provided, uses x-client-token/client credentials)

        Returns:
            LogResponse with success status

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "POST",
                self.LOGS_ENDPOINT,
                token,
                data=log_entry.model_dump(exclude_none=True),
            )
        else:
            response = await self.http_client.post(
                self.LOGS_ENDPOINT, data=log_entry.model_dump(exclude_none=True)
            )
        return LogResponse(**response)

    async def send_batch_logs(
        self, logs: list[LogEntry], token: Optional[str] = None
    ) -> BatchLogResponse:
        """
        Send multiple log entries in batch (POST).

        Supports Bearer token, x-client-token, or client credentials authentication.
        If token is provided, uses authenticated_request. Otherwise uses client credentials (automatic).

        Args:
            logs: List of LogEntry objects
            token: Optional user token (if not provided, uses x-client-token/client credentials)

        Returns:
            BatchLogResponse with processing results

        Raises:
            MisoClientError: If request fails
        """
        request_data = BatchLogRequest(logs=logs)
        if token:
            response = await self.http_client.authenticated_request(
                "POST",
                self.LOGS_BATCH_ENDPOINT,
                token,
                data=request_data.model_dump(exclude_none=True),
            )
        else:
            response = await self.http_client.post(
                self.LOGS_BATCH_ENDPOINT, data=request_data.model_dump(exclude_none=True)
            )
        return BatchLogResponse(**response)
