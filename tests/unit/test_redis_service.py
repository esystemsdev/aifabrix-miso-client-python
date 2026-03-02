"""Unit tests for RedisService logging helpers."""

from miso_client.errors import MisoClientError
from miso_client.models.error_response import ErrorResponse
from miso_client.services.redis import _error_extra


def test_error_extra_extracts_correlation_id_from_structured_error():
    """Build logger extra payload from structured error correlation ID."""
    error_response = ErrorResponse(
        errors=["Redis failure"],
        type="/Errors/Connection",
        statusCode=503,
        correlationId="corr-redis-123",
    )
    error = MisoClientError("Redis failure", status_code=503, error_response=error_response)

    assert _error_extra(error) == {"correlationId": "corr-redis-123"}


def test_error_extra_returns_none_without_correlation_id():
    """Return None when exception has no correlation context."""
    error = Exception("plain redis error")

    assert _error_extra(error) is None
