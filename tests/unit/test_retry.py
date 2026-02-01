"""Tests for execution.retry module - retry logic."""

from unittest.mock import AsyncMock

import pytest

from pytest_aitest.core.errors import RateLimitError
from pytest_aitest.execution.retry import RetryConfig, with_retry


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self) -> None:
        """Default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay_ms == 1000
        assert config.max_delay_ms == 30000
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self) -> None:
        """Custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay_ms=500,
            max_delay_ms=10000,
            exponential_base=1.5,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.base_delay_ms == 500

    def test_compute_delay_no_jitter(self) -> None:
        """Compute delay without jitter."""
        config = RetryConfig(base_delay_ms=1000, exponential_base=2.0, jitter=False)

        # attempt 0: 1000ms * 2^0 = 1000ms = 1s
        assert config.compute_delay(0) == 1.0

        # attempt 1: 1000ms * 2^1 = 2000ms = 2s
        assert config.compute_delay(1) == 2.0

        # attempt 2: 1000ms * 2^2 = 4000ms = 4s
        assert config.compute_delay(2) == 4.0

    def test_compute_delay_respects_max(self) -> None:
        """Delay is capped at max_delay_ms."""
        config = RetryConfig(
            base_delay_ms=10000, max_delay_ms=15000, exponential_base=2.0, jitter=False
        )

        # attempt 2: 10000ms * 2^2 = 40000ms, capped to 15000ms = 15s
        assert config.compute_delay(2) == 15.0

    def test_compute_delay_uses_retry_after(self) -> None:
        """Server-specified retry_after takes precedence."""
        config = RetryConfig(base_delay_ms=1000, jitter=False)

        # retry_after should override computed delay
        assert config.compute_delay(0, retry_after=5.0) == 5.0
        assert config.compute_delay(5, retry_after=1.0) == 1.0

    def test_compute_delay_with_jitter_varies(self) -> None:
        """Jitter adds randomness to delay."""
        config = RetryConfig(base_delay_ms=1000, jitter=True)

        delays = [config.compute_delay(0) for _ in range(10)]
        # With jitter, delays should vary
        # Base is 1s, jitter adds 0-25% = 1.0-1.25s
        assert all(1.0 <= d <= 1.25 for d in delays)
        # At least some variation expected
        assert len(set(delays)) > 1


class TestWithRetry:
    """Tests for with_retry async function."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self) -> None:
        """Successful call returns immediately."""
        func = AsyncMock(return_value="success")

        result = await with_retry(func)

        assert result == "success"
        func.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit(self) -> None:
        """Retries when RateLimitError is raised."""
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError()
            return "success"

        config = RetryConfig(max_retries=3, base_delay_ms=10, jitter=False)
        result = await with_retry(flaky, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        """Raises exception after max retries exhausted."""

        async def always_fails() -> str:
            raise RateLimitError()

        config = RetryConfig(max_retries=2, base_delay_ms=10, jitter=False)

        with pytest.raises(RateLimitError):
            await with_retry(always_fails, config=config)

    @pytest.mark.asyncio
    async def test_does_not_retry_other_exceptions(self) -> None:
        """Non-RateLimitError exceptions are not retried."""
        call_count = 0

        async def fails_differently() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a rate limit")

        config = RetryConfig(max_retries=3, base_delay_ms=10)

        with pytest.raises(ValueError, match="Not a rate limit"):
            await with_retry(fails_differently, config=config)

        # Should only be called once (no retry)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        """on_retry callback is called before each retry."""
        retries: list[tuple[int, Exception, float]] = []

        def track_retry(attempt: int, exc: Exception, delay: float) -> None:
            retries.append((attempt, exc, delay))

        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError()
            return "done"

        config = RetryConfig(max_retries=3, base_delay_ms=10, jitter=False)
        await with_retry(flaky, config=config, on_retry=track_retry)

        assert len(retries) == 2  # Two retries before success
        assert retries[0][0] == 0  # First retry attempt
        assert retries[1][0] == 1  # Second retry attempt
        assert all(isinstance(r[1], RateLimitError) for r in retries)

    @pytest.mark.asyncio
    async def test_uses_retry_after_from_exception(self) -> None:
        """Uses retry_after from RateLimitError if present."""
        delay_used: list[float] = []

        def track_delay(attempt: int, exc: Exception, delay: float) -> None:
            delay_used.append(delay)

        call_count = 0

        async def rate_limited() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=0.1)  # 100ms
            return "done"

        config = RetryConfig(base_delay_ms=10000, jitter=False)  # Would be 10s normally
        await with_retry(rate_limited, config=config, on_retry=track_delay)

        # Should use the retry_after value (0.1s) not the base delay (10s)
        assert delay_used[0] == 0.1
