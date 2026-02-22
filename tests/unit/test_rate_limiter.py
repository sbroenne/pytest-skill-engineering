"""Unit tests for rate limiter."""

from __future__ import annotations

import time

import pytest

from pytest_skill_engineering.execution.rate_limiter import (
    RateLimiter,
    get_rate_limiter,
    reset_rate_limiters,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_rate_limiters()

    def test_no_limits(self) -> None:
        """Limiter with no limits has_limits=False."""
        limiter = RateLimiter()
        assert not limiter.has_limits

    def test_rpm_only(self) -> None:
        """Limiter with only rpm has_limits=True."""
        limiter = RateLimiter(rpm=10)
        assert limiter.has_limits

    def test_tpm_only(self) -> None:
        """Limiter with only tpm has_limits=True."""
        limiter = RateLimiter(tpm=5000)
        assert limiter.has_limits

    def test_both_limits(self) -> None:
        """Limiter with both rpm and tpm has_limits=True."""
        limiter = RateLimiter(rpm=10, tpm=5000)
        assert limiter.has_limits

    @pytest.mark.asyncio
    async def test_acquire_no_limits_returns_immediately(self) -> None:
        """Acquire with no limits should return immediately."""
        limiter = RateLimiter()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_acquire_rpm_under_limit(self) -> None:
        """Acquire under rpm limit should not wait."""
        limiter = RateLimiter(rpm=5)
        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_acquire_rpm_at_limit_waits(self) -> None:
        """Acquire at rpm limit should wait for window to expire."""
        limiter = RateLimiter(rpm=2)
        # Use a short window for testing
        limiter.WINDOW_SECONDS = 0.5

        await limiter.acquire()
        await limiter.acquire()
        # Third acquire should wait
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.3  # Should have waited ~0.5s

    @pytest.mark.asyncio
    async def test_record_tokens(self) -> None:
        """record_tokens stores token records."""
        limiter = RateLimiter(tpm=1000)
        limiter.record_tokens(500)
        assert len(limiter._token_records) == 1
        assert limiter._token_records[0][1] == 500

    @pytest.mark.asyncio
    async def test_record_tokens_no_tpm(self) -> None:
        """record_tokens is no-op when tpm is None."""
        limiter = RateLimiter(rpm=10)
        limiter.record_tokens(500)
        assert len(limiter._token_records) == 0

    @pytest.mark.asyncio
    async def test_record_tokens_zero(self) -> None:
        """record_tokens ignores zero tokens."""
        limiter = RateLimiter(tpm=1000)
        limiter.record_tokens(0)
        assert len(limiter._token_records) == 0

    @pytest.mark.asyncio
    async def test_tpm_under_limit(self) -> None:
        """Acquire under tpm limit should not wait."""
        limiter = RateLimiter(tpm=1000)
        limiter.record_tokens(500)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_tpm_at_limit_waits(self) -> None:
        """Acquire at tpm limit should wait for window to expire."""
        limiter = RateLimiter(tpm=1000)
        limiter.WINDOW_SECONDS = 0.5

        limiter.record_tokens(1000)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.3  # Should have waited ~0.5s


class TestGetRateLimiter:
    """Tests for get_rate_limiter factory function."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_rate_limiters()

    def test_creates_new_limiter(self) -> None:
        """Creates a new limiter for unknown model."""
        limiter = get_rate_limiter("azure/gpt-5-mini", rpm=10)
        assert limiter.rpm == 10
        assert limiter.tpm is None

    def test_returns_same_limiter(self) -> None:
        """Returns same limiter instance for same model."""
        limiter1 = get_rate_limiter("azure/gpt-5-mini", rpm=10)
        limiter2 = get_rate_limiter("azure/gpt-5-mini", rpm=10)
        assert limiter1 is limiter2

    def test_takes_most_restrictive_rpm(self) -> None:
        """When called with different rpm, takes the minimum."""
        get_rate_limiter("azure/gpt-5-mini", rpm=20)
        limiter = get_rate_limiter("azure/gpt-5-mini", rpm=10)
        assert limiter.rpm == 10

    def test_takes_most_restrictive_tpm(self) -> None:
        """When called with different tpm, takes the minimum."""
        get_rate_limiter("azure/gpt-5-mini", tpm=50000)
        limiter = get_rate_limiter("azure/gpt-5-mini", tpm=10000)
        assert limiter.tpm == 10000

    def test_adds_limit_to_existing(self) -> None:
        """Can add tpm to a limiter that only had rpm."""
        get_rate_limiter("azure/gpt-5-mini", rpm=10)
        limiter = get_rate_limiter("azure/gpt-5-mini", tpm=5000)
        assert limiter.rpm == 10
        assert limiter.tpm == 5000

    def test_different_models_separate_limiters(self) -> None:
        """Different models get separate limiters."""
        limiter1 = get_rate_limiter("azure/gpt-5-mini", rpm=10)
        limiter2 = get_rate_limiter("azure/gpt-4.1", rpm=20)
        assert limiter1 is not limiter2
        assert limiter1.rpm == 10
        assert limiter2.rpm == 20

    def test_no_limits_creates_limiter(self) -> None:
        """Creates limiter even with no limits (has_limits=False)."""
        limiter = get_rate_limiter("azure/gpt-5-mini")
        assert not limiter.has_limits

    def test_reset_clears_all(self) -> None:
        """reset_rate_limiters clears all cached limiters."""
        limiter1 = get_rate_limiter("azure/gpt-5-mini", rpm=10)
        reset_rate_limiters()
        limiter2 = get_rate_limiter("azure/gpt-5-mini", rpm=20)
        assert limiter1 is not limiter2
        assert limiter2.rpm == 20  # Not constrained by old value
