"""Token-based cost estimation for LLM calls.

Pricing lookup order:

1. **User overrides** from ``pricing.toml`` — checked first so users can add
   pricing for models missing from litellm or correct stale entries.
2. **litellm ``model_cost``** — exact key match against litellm's comprehensive
   auto-maintained pricing map (2500+ models).
3. **Dated-version fallback** — if no exact match exists and the model string
   does *not* already end with a ``-YYYYMMDD`` date, search litellm for keys
   matching ``{model}-YYYYMMDD``.  If exactly **one** dated variant is found,
   use its pricing.  Handles cases like ``claude-sonnet-4`` (user-specified)
   resolving to ``claude-sonnet-4-20250514`` (litellm key).

Models without pricing in any source return ``0.0`` and are tracked in
:data:`models_without_pricing` so downstream code (AI insights) can warn
that cost-based analysis is unreliable.

``pricing.toml`` format::

    # Per-million-token pricing.
    [models]
    "claude-sonnet-4" = { input = 3.00, output = 15.00 }
    "azure/my-custom-deploy" = { input = 2.00, output = 8.00 }
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from litellm import model_cost

_logger = logging.getLogger(__name__)

# Models that callers asked about but had no pricing anywhere.
# Populated at runtime by :func:`estimate_cost`.
models_without_pricing: set[str] = set()

# ── User overrides (pricing.toml) ────────────────────────────────────────────

_user_overrides: dict[str, tuple[float, float]] | None = None


def _load_user_overrides() -> dict[str, tuple[float, float]]:
    """Load per-million-token overrides from ``pricing.toml``.

    Searches upward from cwd for the first ``pricing.toml`` found.
    Returns an empty dict when no file exists.
    """
    global _user_overrides  # noqa: PLW0603
    if _user_overrides is not None:
        return _user_overrides

    _user_overrides = {}
    toml_path = _find_pricing_toml()
    if toml_path is None:
        return _user_overrides

    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib  # type: ignore[no-redef]

    try:
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        models_section: dict[str, Any] = raw.get("models", {})
        for key, value in models_section.items():
            if isinstance(value, dict):
                input_pm = float(value.get("input", 0))
                output_pm = float(value.get("output", 0))
                _user_overrides[key] = (input_pm, output_pm)
        if _user_overrides:
            _logger.info(
                "Loaded %d pricing override(s) from %s",
                len(_user_overrides),
                toml_path,
            )
    except Exception:
        _logger.warning("Failed to parse %s; ignoring", toml_path, exc_info=True)

    return _user_overrides


def _find_pricing_toml() -> Path | None:
    """Walk upward from cwd looking for ``pricing.toml``."""
    current = Path.cwd().resolve()
    for parent in (current, *current.parents):
        candidate = parent / "pricing.toml"
        if candidate.is_file():
            return candidate
    return None


# Pattern matching a trailing date suffix like -20250514.
_DATE_SUFFIX_RE = re.compile(r"-\d{8}$")

# Cache: dateless model → litellm key (or None if ambiguous/missing).
_dated_fallback_cache: dict[str, str | None] = {}


def _find_dated_variant(model: str) -> str | None:
    """Find exactly one ``{model}-YYYYMMDD`` key in litellm.

    Returns the dated key when exactly one match exists, ``None`` otherwise.
    Results are cached so repeated calls for the same model avoid re-scanning.
    """
    cached = _dated_fallback_cache.get(model)
    if cached is not None or model in _dated_fallback_cache:
        return cached

    # Match "{model}-YYYYMMDD" exactly — no extra segments between model and date.
    dated_re = re.compile(re.escape(model) + r"-\d{8}$")
    matches = [k for k in model_cost if dated_re.fullmatch(k)]
    result = matches[0] if len(matches) == 1 else None
    _dated_fallback_cache[model] = result

    if result:
        _logger.debug("Dated fallback: %r → %r", model, result)
    elif len(matches) > 1:
        _logger.debug(
            "Dated fallback: %r has %d matches — ambiguous, skipping",
            model,
            len(matches),
        )

    return result


# ── Public API ───────────────────────────────────────────────────────────────


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for a single LLM call.

    Checks user overrides (``pricing.toml``) first, then litellm.
    Returns ``0.0`` and records the model in :data:`models_without_pricing`
    when no pricing is found in either source.
    """
    if input_tokens == 0 and output_tokens == 0:
        return 0.0

    # 1. User overrides (per-million-token pricing)
    overrides = _load_user_overrides()
    pricing = overrides.get(model)
    if pricing is not None:
        return (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000

    # 2. litellm exact match (per-token pricing)
    info = model_cost.get(model)
    if info is None and not _DATE_SUFFIX_RE.search(model):
        # 3. Dated-version fallback: "model" → "model-YYYYMMDD" (exactly one)
        dated_key = _find_dated_variant(model)
        if dated_key:
            info = model_cost.get(dated_key)

    if info is not None:
        input_rate = info.get("input_cost_per_token", 0.0) or 0.0
        output_rate = info.get("output_cost_per_token", 0.0) or 0.0
        return input_tokens * input_rate + output_tokens * output_rate

    # No pricing found
    models_without_pricing.add(model)
    _logger.debug("No pricing data for model %r; cost will be 0", model)
    return 0.0
