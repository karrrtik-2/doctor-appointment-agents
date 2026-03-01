"""
Circuit breaker pattern for agent/tool failure recovery.

States:
  CLOSED   → Normal operation, failures counted
  OPEN     → Requests fast-fail, waiting for recovery timeout
  HALF_OPEN → Limited test requests to probe recovery

Prevents cascading failures when downstream services
(LLM APIs, databases) are unhealthy.
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Optional

from infrastructure.audit.logger import get_audit_logger


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit is open and request is rejected."""
    pass


class CircuitBreaker:
    """
    Per-service circuit breaker with configurable thresholds.

    Usage:
        cb = CircuitBreaker("llm_api", failure_threshold=5, recovery_timeout=60)
        result = cb.call(lambda: llm.invoke(prompt))
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 2,
    ):
        self.name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0
        self._lock = threading.Lock()
        self._audit = get_audit_logger()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute func through the circuit breaker.
        Raises CircuitBreakerOpenError if circuit is open.
        """
        with self._lock:
            self._check_state_transition()

            if self._state == CircuitState.OPEN:
                self._audit.log_event(
                    "circuit_breaker_rejected",
                    details={"breaker": self.name, "state": self._state.value},
                    severity="warning",
                    source="resilience",
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Recovery in {self._time_until_recovery():.0f}s."
                )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' HALF_OPEN limit reached."
                    )
                self._half_open_calls += 1

        # Execute outside lock
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._on_failure(exc)
            raise
        else:
            self._on_success()
            return result

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            self._audit.log_event(
                "circuit_breaker_failure",
                details={
                    "breaker": self.name,
                    "state": self._state.value,
                    "failure_count": self._failure_count,
                    "error": str(exc),
                },
                severity="warning",
                source="resilience",
            )

    def _check_state_transition(self) -> None:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self._recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0

        self._audit.log_event(
            "circuit_breaker_transition",
            details={
                "breaker": self.name,
                "from_state": old_state.value,
                "to_state": new_state.value,
                "failure_count": self._failure_count,
            },
            severity="info",
            source="resilience",
        )

    def _time_until_recovery(self) -> float:
        elapsed = time.time() - self._last_failure_time
        return max(0, self._recovery_timeout - elapsed)

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            self._check_state_transition()
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "time_until_recovery": self._time_until_recovery() if self._state == CircuitState.OPEN else 0,
            }


# ── Registry of circuit breakers per service ────────────────────

_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(
    name: str = "llm_api",
    failure_threshold: Optional[int] = None,
    recovery_timeout: Optional[int] = None,
    half_open_max_calls: Optional[int] = None,
) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    with _breakers_lock:
        if name not in _breakers:
            from config.settings import get_settings
            settings = get_settings()
            _breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold or settings.circuit_breaker_failure_threshold,
                recovery_timeout=recovery_timeout or settings.circuit_breaker_recovery_timeout,
                half_open_max_calls=half_open_max_calls or settings.circuit_breaker_half_open_max_calls,
            )
        return _breakers[name]
