"""Shared fixtures and constants for Copilot integration tests."""

from __future__ import annotations

import os
import subprocess

import pytest
from pydantic_ai import Agent as Eval

from pytest_skill_engineering.execution.pydantic_adapter import build_model_from_string

# Default model — None means Copilot picks its default
DEFAULT_MODEL: str | None = None

# Models for parametrized tests
MODELS: list[str] = ["gpt-5.2", "claude-opus-4.5"]

# Timeouts
DEFAULT_TIMEOUT_S: float = 300.0

# Turn limits
DEFAULT_MAX_TURNS: int = 25


def _has_github_auth() -> bool:
    """Check whether GitHub auth is available for Copilot-backed models."""
    if os.environ.get("GITHUB_TOKEN"):
        return True
    try:
        result = subprocess.run(  # noqa: S603
            ["gh", "auth", "status"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _candidate_judge_models() -> list[str]:
    """Build ordered model candidates from available providers."""
    override = os.environ.get("AITEST_INTEGRATION_JUDGE_MODEL")
    if override:
        return [override]

    candidates: list[str] = []
    if os.environ.get("AZURE_API_BASE") or os.environ.get("AZURE_OPENAI_ENDPOINT"):
        candidates.append("azure/gpt-5-mini")
    if os.environ.get("OPENAI_API_KEY"):
        candidates.append("openai/gpt-5-mini")
    if _has_github_auth():
        candidates.append("copilot/gpt-5-mini")
    return candidates


@pytest.fixture(scope="session")
async def integration_judge_model() -> str:
    """Return a verified accessible model for integration judge calls.

    Fails loudly when no configured provider can serve a minimal request.
    """
    candidates = _candidate_judge_models()
    if not candidates:
        pytest.fail(
            "No model provider configured for integration judge calls. "
            "Set one of: AZURE_API_BASE/AZURE_OPENAI_ENDPOINT, OPENAI_API_KEY, "
            "or GitHub auth (GITHUB_TOKEN or `gh auth login`)."
        )

    errors: list[str] = []
    for model_str in candidates:
        try:
            model = build_model_from_string(model_str)
            agent = Eval(model)
            result = await agent.run("Reply with exactly: OK")
            if "OK" in result.output:
                return model_str
            errors.append(f"{model_str}: unexpected probe output {result.output!r}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{model_str}: {exc}")

    joined = "\n- ".join(errors)
    pytest.fail(f"Model access probe failed for all configured providers:\n- {joined}")
