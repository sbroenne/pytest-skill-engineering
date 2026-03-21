"""Token-based cost estimation for LLM calls.

Pricing lookup uses ``pricing.toml`` — a user-maintained file with per-million-token
pricing for models. Models without pricing return ``0.0``.

``pricing.toml`` format::

    # Per-million-token pricing.
    [models]
    "claude-sonnet-4" = { input = 3.00, output = 15.00 }
    "azure/my-custom-deploy" = { input = 2.00, output = 8.00 }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

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


# ── Public API ───────────────────────────────────────────────────────────────


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for a single LLM call.

    Checks user overrides (``pricing.toml``).
    Returns ``0.0`` and records the model in :data:`models_without_pricing`
    when no pricing is found.
    """
    if input_tokens == 0 and output_tokens == 0:
        return 0.0

    overrides = _load_user_overrides()
    pricing = overrides.get(model)
    if pricing is not None:
        return (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000

    # No pricing found
    models_without_pricing.add(model)
    _logger.debug("No pricing data for model %r; cost will be 0", model)
    return 0.0
