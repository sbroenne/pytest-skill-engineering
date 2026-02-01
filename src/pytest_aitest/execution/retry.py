"""Retry logic for transient failures."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from pytest_aitest.core.errors import RateLimitError

T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class RetryConfig:
    """Configuration for retry behavior.

    Example:
        config = RetryConfig(max_retries=5, base_delay_ms=2000)
        result = await with_retry(async_operation, config=config)
    """

    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 30000
    exponential_base: float = 2.0
    jitter: bool = True

    def compute_delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Compute delay in seconds for the given attempt.

        Args:
            attempt: Current attempt number (0-indexed)
            retry_after: Optional server-specified delay in seconds

        Returns:
            Delay in seconds to wait before retry
        """
        if retry_after is not None:
            return retry_after

        delay_ms = self.base_delay_ms * (self.exponential_base**attempt)
        delay_ms = min(delay_ms, self.max_delay_ms)

        if self.jitter:
            # Add random jitter (0-25% of delay)
            jitter_ms = random.uniform(0, delay_ms * 0.25)
            delay_ms += jitter_ms

        return delay_ms / 1000


async def with_retry(
    func: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Execute an async function with retry logic.

    Args:
        func: Async function to execute
        config: Retry configuration (uses defaults if None)
        on_retry: Optional callback called before each retry (attempt, exception, delay)

    Returns:
        Result of successful function call

    Raises:
        Exception: The last exception if all retries fail
    """
    config = config or RetryConfig()
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except RateLimitError as e:
            last_exception = e
            if attempt == config.max_retries:
                raise

            delay = config.compute_delay(attempt, e.retry_after)
            if on_retry:
                on_retry(attempt, e, delay)
            await asyncio.sleep(delay)
        except Exception:
            # Don't retry other exceptions
            raise

    # Should never reach here, but satisfy type checker
    assert last_exception is not None
    raise last_exception
