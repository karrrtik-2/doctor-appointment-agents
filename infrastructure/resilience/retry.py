"""
Retry with exponential backoff and jitter.

Configurable retry strategy for transient failures
in LLM API calls, tool executions, and external services.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence, Type

logger = logging.getLogger("platform.resilience.retry")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,)


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: Optional[tuple[Type[Exception], ...]] = None,
):
    """
    Decorator — retries a function with exponential backoff.

    Usage:
        @retry_with_backoff(max_attempts=3)
        def call_llm(prompt):
            return llm.invoke(prompt)
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            retryable_exceptions=retryable_exceptions or (Exception,),
        )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as exc:
                    last_exception = exc
                    if attempt == config.max_attempts:
                        logger.error(
                            "All %d retry attempts exhausted for %s: %s",
                            config.max_attempts,
                            func.__name__,
                            exc,
                        )
                        raise

                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay,
                    )
                    if config.jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        "Retry %d/%d for %s after %.1fs: %s",
                        attempt,
                        config.max_attempts,
                        func.__name__,
                        delay,
                        exc,
                    )
                    time.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator
