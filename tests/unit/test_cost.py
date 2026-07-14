"""Pure-logic tests for token-based cost estimation.

No LLM calls — these exercise the arithmetic and pricing lookup in
``execution.cost`` directly.
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.execution import cost


@pytest.fixture
def pricing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a deterministic pricing table and reset module globals."""
    overrides = {
        # (input, output, cache_read) per million tokens
        "priced-model": (10.0, 30.0, 1.0),
        "no-cache-model": (10.0, 30.0, 0.0),
    }
    monkeypatch.setattr(cost, "_user_overrides", overrides)
    monkeypatch.setattr(cost, "models_without_pricing", set())


def test_basic_input_output_cost(pricing: None) -> None:
    # 1M input @ $10 + 1M output @ $30 = $40
    assert cost.estimate_cost("priced-model", 1_000_000, 1_000_000) == pytest.approx(40.0)


def test_cache_read_tokens_are_priced(pricing: None) -> None:
    # 1M cache-read tokens @ $1 add exactly $1 on top of input/output.
    without = cost.estimate_cost("priced-model", 1_000_000, 0, 0)
    with_cache = cost.estimate_cost("priced-model", 1_000_000, 0, 1_000_000)
    assert with_cache - without == pytest.approx(1.0)


def test_cache_read_default_is_zero(pricing: None) -> None:
    # Omitting cache_read_tokens must not change the estimate.
    explicit = cost.estimate_cost("priced-model", 500_000, 500_000, 0)
    implicit = cost.estimate_cost("priced-model", 500_000, 500_000)
    assert explicit == implicit


def test_cache_read_ignored_when_rate_unset(pricing: None) -> None:
    # A model with cache_read rate 0.0 prices cache tokens at nothing.
    assert cost.estimate_cost("no-cache-model", 0, 0, 1_000_000) == pytest.approx(0.0)


def test_unknown_model_returns_zero_and_is_recorded(pricing: None) -> None:
    assert cost.estimate_cost("mystery-model", 1_000, 1_000) == 0.0
    assert "mystery-model" in cost.models_without_pricing


def test_all_zero_tokens_short_circuits(pricing: None) -> None:
    assert cost.estimate_cost("priced-model", 0, 0, 0) == 0.0
