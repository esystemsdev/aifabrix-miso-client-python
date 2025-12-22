"""
Unit tests for circuit breaker.
"""

import time

from miso_client.models.config import CircuitBreakerConfig
from miso_client.utils.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Test cases for circuit breaker."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.get_state() == CircuitState.CLOSED
        assert breaker.is_open() is False

    def test_circuit_breaker_custom_config(self):
        """Test circuit breaker with custom configuration."""
        config = CircuitBreakerConfig(failureThreshold=5, resetTimeout=120)
        breaker = CircuitBreaker(config)
        assert breaker.failure_threshold == 5
        assert breaker.reset_timeout == 120

    def test_circuit_breaker_default_config(self):
        """Test circuit breaker with default configuration."""
        breaker = CircuitBreaker()
        assert breaker.failure_threshold == 3
        assert breaker.reset_timeout == 60

    def test_circuit_breaker_record_success(self):
        """Test recording success resets failure count."""
        breaker = CircuitBreaker()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.get_state() == CircuitState.CLOSED

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker()
        breaker.record_failure()
        assert breaker.get_state() == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.get_state() == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.get_state() == CircuitState.OPEN
        assert breaker.is_open() is True

    def test_circuit_breaker_resets_after_timeout(self):
        """Test circuit resets after timeout period."""
        config = CircuitBreakerConfig(failureThreshold=1, resetTimeout=1)
        breaker = CircuitBreaker(config)
        breaker.record_failure()
        assert breaker.get_state() == CircuitState.OPEN
        assert breaker.is_open() is True

        # Wait for reset timeout
        time.sleep(1.1)

        # Circuit should transition to HALF_OPEN, then allow requests
        assert breaker.is_open() is False

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit recovers from HALF_OPEN state."""
        config = CircuitBreakerConfig(failureThreshold=1, resetTimeout=1)
        breaker = CircuitBreaker(config)
        breaker.record_failure()
        assert breaker.get_state() == CircuitState.OPEN

        # Wait for reset timeout
        time.sleep(1.1)

        # Check state (should be HALF_OPEN after timeout)
        breaker.is_open()  # This triggers state transition
        assert (
            breaker.get_state() == CircuitState.HALF_OPEN
            or breaker.get_state() == CircuitState.CLOSED
        )

        # Record success to close circuit
        breaker.record_success()
        assert breaker.get_state() == CircuitState.CLOSED

    def test_circuit_breaker_reset(self):
        """Test manual circuit reset."""
        breaker = CircuitBreaker()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.get_state() == CircuitState.OPEN

        breaker.reset()
        assert breaker.get_state() == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_circuit_breaker_is_open_when_open(self):
        """Test is_open returns True when circuit is OPEN."""
        breaker = CircuitBreaker()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open() is True

    def test_circuit_breaker_is_open_when_closed(self):
        """Test is_open returns False when circuit is CLOSED."""
        breaker = CircuitBreaker()
        assert breaker.is_open() is False
