"""Pure-logic tests for token-based cost estimation.

No LLM calls — these exercise the arithmetic and pricing lookup in
``execution.cost`` directly.
"""

from __future__ import annotations

import os
from pathlib import Path

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


@pytest.fixture
def reset_pricing_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cost, "_user_overrides_cache", {})
    monkeypatch.setattr(cost, "_user_overrides_cache_key", None)
    monkeypatch.setattr(cost, "_user_overrides", None)


def test_pricing_cache_isolated_by_resolved_file_and_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_pricing_cache: None
) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()
    pricing_a = repo_a / "pricing.toml"
    pricing_b = repo_b / "pricing.toml"
    pricing_a.write_text('[models]\n"model" = { input = 1, output = 2, cache_read = 3 }\n')
    pricing_b.write_text('[models]\n"model" = { input = 4, output = 5, cache_read = 6 }\n')

    monkeypatch.chdir(repo_a)
    assert cost._load_user_overrides()["model"] == (1.0, 2.0, 3.0)

    monkeypatch.chdir(repo_b)
    assert cost._load_user_overrides()["model"] == (4.0, 5.0, 6.0)
    assert set(path for path, _mtime in cost._user_overrides_cache) == {
        pricing_a.resolve(),
        pricing_b.resolve(),
    }


def test_pricing_cache_invalidates_when_pricing_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_pricing_cache: None
) -> None:
    pricing = tmp_path / "pricing.toml"
    pricing.write_text('[models]\n"model" = { input = 1, output = 2, cache_read = 3 }\n')
    monkeypatch.chdir(tmp_path)

    assert cost._load_user_overrides()["model"] == (1.0, 2.0, 3.0)

    pricing.write_text('[models]\n"model" = { input = 7, output = 8, cache_read = 9 }\n')
    stat = pricing.stat()
    os.utime(pricing, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))

    assert cost._load_user_overrides()["model"] == (7.0, 8.0, 9.0)
    assert len(cost._user_overrides_cache) == 2


def test_pricing_cache_key_uses_cwd_when_no_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_pricing_cache: None
) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    monkeypatch.chdir(repo_a)
    assert cost._load_user_overrides() == {}
    key_a = cost._user_overrides_cache_key

    monkeypatch.chdir(repo_b)
    assert cost._load_user_overrides() == {}
    key_b = cost._user_overrides_cache_key

    assert key_a == (repo_a.resolve(), None)
    assert key_b == (repo_b.resolve(), None)
    assert len(cost._user_overrides_cache) == 2
