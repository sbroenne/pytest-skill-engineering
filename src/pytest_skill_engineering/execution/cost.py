"""Token-based cost estimation for LLM calls.

Pricing lookup uses ``pricing.toml`` — a user-maintained file with per-million-token
pricing for models. Models without pricing return ``0.0``.

``pricing.toml`` format::

    # Per-million-token pricing. ``cache_read`` is optional (defaults to 0.0)
    # and prices cached-prompt input tokens, which most vendors bill at a
    # fraction of the normal input rate.
    [models]
    "claude-sonnet-4" = { input = 3.00, output = 15.00, cache_read = 0.30 }
    "copilot/gpt-5.4-mini" = { input = 2.00, output = 8.00 }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

# Models that callers asked about but had no pricing anywhere.
# Populated at runtime by :func:`estimate_cost`.
models_without_pricing: set[str] = set()

# ── User overrides (pricing.toml) ────────────────────────────────────────────

Pricing = tuple[float, float, float]
PricingTable = dict[str, Pricing]
PricingCacheKey = tuple[Path, int | None]


@dataclass(slots=True)
class _PricingCache:
    """Pricing tables keyed by resolved file identity and modification time."""

    tables: dict[PricingCacheKey, PricingTable] = field(default_factory=dict)

    def load(self, current_dir: Path) -> PricingTable:
        toml_path = _find_pricing_toml(current_dir)
        cache_key = _pricing_cache_key(current_dir, toml_path)
        cached = self.tables.get(cache_key)
        if cached is not None:
            return cached

        overrides = _read_pricing_file(toml_path)
        self.tables[cache_key] = overrides
        return overrides

    def clear(self) -> None:
        """Discard all cached pricing tables."""
        self.tables.clear()


_pricing_cache = _PricingCache()


def _load_user_overrides() -> PricingTable:
    """Load per-million-token overrides from ``pricing.toml``.

    Searches upward from cwd for the first ``pricing.toml`` found.
    Returns an empty dict when no file exists.
    """
    current_dir = Path.cwd().resolve()
    return _pricing_cache.load(current_dir)


def _read_pricing_file(toml_path: Path | None) -> PricingTable:
    """Parse a pricing file into per-million-token rates."""
    overrides: PricingTable = {}
    if toml_path is None:
        return overrides

    import tomllib

    try:
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        models_section: dict[str, Any] = raw.get("models", {})
        for key, value in models_section.items():
            if isinstance(value, dict):
                input_pm = float(value.get("input", 0))
                output_pm = float(value.get("output", 0))
                cache_read_pm = float(value.get("cache_read", 0))
                overrides[key] = (input_pm, output_pm, cache_read_pm)
        if overrides:
            _logger.info(
                "Loaded %d pricing override(s) from %s",
                len(overrides),
                toml_path,
            )
    except (
        AttributeError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
        tomllib.TOMLDecodeError,
    ):
        _logger.warning("Failed to parse %s; ignoring", toml_path, exc_info=True)

    return overrides


def _pricing_cache_key(current_dir: Path, toml_path: Path | None) -> PricingCacheKey:
    """Build a cache key scoped to the active cwd and pricing file version."""
    if toml_path is None:
        return current_dir, None
    stat = toml_path.stat()
    return toml_path.resolve(), stat.st_mtime_ns


def _find_pricing_toml(current_dir: Path) -> Path | None:
    """Walk upward from cwd looking for ``pricing.toml``."""
    for parent in (current_dir, *current_dir.parents):
        candidate = parent / "pricing.toml"
        if candidate.is_file():
            return candidate
    return None


# ── Public API ───────────────────────────────────────────────────────────────


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> float:
    """Return estimated USD cost for a single LLM call.

    Checks user overrides (``pricing.toml``). ``cache_read_tokens`` are priced
    at the model's optional ``cache_read`` rate (``0.0`` when unset, so they add
    nothing unless a rate is configured).
    Returns ``0.0`` and records the model in :data:`models_without_pricing`
    when no pricing is found.
    """
    if input_tokens == 0 and output_tokens == 0 and cache_read_tokens == 0:
        return 0.0

    overrides = _load_user_overrides()
    pricing = overrides.get(model)
    if pricing is not None:
        return (
            input_tokens * pricing[0] + output_tokens * pricing[1] + cache_read_tokens * pricing[2]
        ) / 1_000_000

    # No pricing found
    models_without_pricing.add(model)
    _logger.debug("No pricing data for model %r; cost will be 0", model)
    return 0.0
