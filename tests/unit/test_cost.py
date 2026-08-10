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
def pricing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a deterministic pricing file."""
    (tmp_path / "pricing.toml").write_text(
        "[models]\n"
        '"priced-model" = { input = 10, output = 30, cache_read = 1 }\n'
        '"no-cache-model" = { input = 10, output = 30 }\n'
    )
    monkeypatch.chdir(tmp_path)
    cost._pricing_cache.clear()
    cost.models_without_pricing.clear()


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
def reset_pricing_cache() -> None:
    cost._pricing_cache.clear()


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
    assert set(path for path, _mtime in cost._pricing_cache.tables) == {
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
    assert len(cost._pricing_cache.tables) == 2


def test_pricing_cache_key_uses_cwd_when_no_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reset_pricing_cache: None
) -> None:
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    monkeypatch.chdir(repo_a)
    assert cost._load_user_overrides() == {}
    monkeypatch.chdir(repo_b)
    assert cost._load_user_overrides() == {}
    assert set(cost._pricing_cache.tables) == {
        (repo_a.resolve(), None),
        (repo_b.resolve(), None),
    }
