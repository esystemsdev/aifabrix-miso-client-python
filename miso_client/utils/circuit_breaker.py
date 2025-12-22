"""
Circuit breaker implementation for HTTP logging.

Prevents infinite retry loops when logging service is unavailable by opening
the circuit after consecutive failures and resetting after a timeout period.
"""

import time
from enum import Enum
from typing import Optional

from ..models.config import CircuitBreakerConfig


class CircuitState(Enum):
    """Circuit breaker state."""

    CLOSED = "CLOSED"  # Normal operation, requests allowed
    OPEN = "OPEN"  # Circuit open, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for HTTP logging.

    Prevents infinite retry loops when logging service is unavailable.
    Opens circuit after consecutive failures and resets after timeout period.

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        reset_timeout: Seconds to wait before resetting circuit
        state: Current circuit state
        failure_count: Current consecutive failure count
        last_failure_time: Timestamp of last failure
        opened_at: Timestamp when circuit was opened
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker with configuration.

        Args:
            config: Circuit breaker configuration (optional)
        """
        if config:
            self.failure_threshold = config.failureThreshold or 3
            self.reset_timeout = config.resetTimeout or 60
        else:
            self.failure_threshold = 3
            self.reset_timeout = 60

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None

    def is_open(self) -> bool:
        """
        Check if circuit is open (requests should be blocked).

        Automatically transitions from OPEN to HALF_OPEN after reset timeout.

        Returns:
            True if circuit is open, False otherwise
        """
        if self.state == CircuitState.CLOSED:
            return False

        if self.state == CircuitState.OPEN:
            # Check if reset timeout has passed
            if self.opened_at and (time.time() - self.opened_at) >= self.reset_timeout:
                # Transition to HALF_OPEN to test if service recovered
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
                return False
            return True

        # HALF_OPEN state - allow requests to test recovery
        return False

    def record_success(self) -> None:
        """
        Record successful request.

        Resets failure count and closes circuit if it was open.
        """
        if self.state == CircuitState.HALF_OPEN:
            # Service recovered, close circuit
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.opened_at = None
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """
        Record failed request.

        Increments failure count and opens circuit if threshold reached.
        """
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            # Open circuit
            self.state = CircuitState.OPEN
            self.opened_at = time.time()

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.opened_at = None

    def get_state(self) -> CircuitState:
        """
        Get current circuit state.

        Returns:
            Current circuit state
        """
        return self.state
