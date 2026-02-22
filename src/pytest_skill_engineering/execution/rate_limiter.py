"""Async rate limiter for LLM API calls.

Provides sliding-window rate limiting for requests per minute (rpm) and
tokens per minute (tpm). Rate limiters are shared across all engine instances
using the same model, so concurrent tests respect deployment limits.

Usage:
    limiter = get_rate_limiter("azure/gpt-5-mini", rpm=10, tpm=10000)
    await limiter.acquire()  # Waits if rate limit would be exceeded
    # ... make API call ...
    limiter.record_tokens(1500)  # Track token usage for tpm enforcement
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

_logger = logging.getLogger(__name__)

# Global registry of rate limiters, keyed by model string.
# Shared across all EvalEngine instances so concurrent tests
# respect the same deployment's rate limits.
_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(
    model: str,
    *,
    rpm: int | None = None,
    tpm: int | None = None,
) -> RateLimiter:
    """Get or create a rate limiter for the given model.

    If a limiter already exists for this model, updates it with the most
    restrictive limits (minimum of old and new values).

    Args:
        model: Model identifier string (e.g. "azure/gpt-5-mini").
        rpm: Requests per minute limit.
        tpm: Tokens per minute limit.

    Returns:
        Shared RateLimiter instance for this model.
    """
    if model not in _rate_limiters:
        _rate_limiters[model] = RateLimiter(rpm=rpm, tpm=tpm)
    else:
        limiter = _rate_limiters[model]
        # Take the most restrictive limit
        if rpm is not None:
            limiter.rpm = min(limiter.rpm, rpm) if limiter.rpm is not None else rpm
        if tpm is not None:
            limiter.tpm = min(limiter.tpm, tpm) if limiter.tpm is not None else tpm
    return _rate_limiters[model]


def reset_rate_limiters() -> None:
    """Reset all rate limiters. Called between test sessions."""
    _rate_limiters.clear()


class RateLimiter:
    """Sliding-window rate limiter for rpm and tpm.

    Uses a 60-second sliding window to track request times and token usage.
    When limits would be exceeded, ``acquire()`` awaits until enough capacity
    is available.

    This rate limiter operates at the engine.run() level — each call to
    ``acquire()`` represents one agent run (which may internally make multiple
    LLM requests across turns). For rpm, this means the limit applies to
    agent runs, not individual LLM calls. This is a pragmatic trade-off:
    true per-LLM-call rate limiting would require wrapping the PydanticAI
    model, which is significantly more complex.

    For tpm, token usage is recorded after each run via ``record_tokens()``,
    and the limiter checks cumulative usage in the sliding window before
    allowing the next run.
    """

    WINDOW_SECONDS: float = 60.0

    def __init__(self, rpm: int | None = None, tpm: int | None = None) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self._request_times: deque[float] = deque()
        self._token_records: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    @property
    def has_limits(self) -> bool:
        """Whether any limits are configured."""
        return self.rpm is not None or self.tpm is not None

    async def acquire(self) -> None:
        """Wait if necessary to stay within rate limits.

        For rpm: checks if we've made too many requests in the last 60 seconds.
        For tpm: checks if token usage in the last 60 seconds exceeds the limit.

        If either limit is exceeded, sleeps until the oldest entry in the
        sliding window expires, freeing capacity.
        """
        if not self.has_limits:
            return

        async with self._lock:
            await self._enforce_rpm()
            await self._enforce_tpm()

    def record_tokens(self, tokens: int) -> None:
        """Record token usage after a run completes.

        Args:
            tokens: Total tokens consumed (input + output).
        """
        if self.tpm is not None and tokens > 0:
            self._token_records.append((time.monotonic(), tokens))

    async def _enforce_rpm(self) -> None:
        """Enforce requests-per-minute limit."""
        if self.rpm is None:
            return

        now = time.monotonic()
        self._prune_old_entries(self._request_times, now)

        if len(self._request_times) >= self.rpm:
            wait_seconds = self._request_times[0] + self.WINDOW_SECONDS - now
            if wait_seconds > 0:
                _logger.info(
                    "Rate limit (rpm=%d): waiting %.1fs before next request",
                    self.rpm,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
                now = time.monotonic()
                self._prune_old_entries(self._request_times, now)

        self._request_times.append(now)

    async def _enforce_tpm(self) -> None:
        """Enforce tokens-per-minute limit."""
        if self.tpm is None:
            return

        now = time.monotonic()
        self._prune_old_token_entries(now)

        total_tokens = sum(tokens for _, tokens in self._token_records)
        if total_tokens >= self.tpm:
            # Wait until the oldest record falls out of the window
            wait_seconds = self._token_records[0][0] + self.WINDOW_SECONDS - now
            if wait_seconds > 0:
                _logger.info(
                    "Rate limit (tpm=%d): waiting %.1fs (current window: %d tokens)",
                    self.tpm,
                    wait_seconds,
                    total_tokens,
                )
                await asyncio.sleep(wait_seconds)
                self._prune_old_token_entries(time.monotonic())

    def _prune_old_entries(self, times: deque[float], now: float) -> None:
        """Remove entries older than the sliding window."""
        cutoff = now - self.WINDOW_SECONDS
        while times and times[0] < cutoff:
            times.popleft()

    def _prune_old_token_entries(self, now: float) -> None:
        """Remove token records older than the sliding window."""
        cutoff = now - self.WINDOW_SECONDS
        while self._token_records and self._token_records[0][0] < cutoff:
            self._token_records.popleft()
