"""Shared fixtures and constants for Copilot integration tests."""

from __future__ import annotations

import subprocess

import pytest

from pytest_skill_engineering.copilot.client import get_github_token

# Default model for integration tests
DEFAULT_MODEL: str = "gpt-5.4-mini"

# Frontier flagship models for parametrized tests
MODELS: list[str] = ["gpt-5.5", "claude-sonnet-5"]

# Timeouts
DEFAULT_TIMEOUT_S: float = 300.0

# Turn limits
DEFAULT_MAX_TURNS: int = 25


def _has_github_auth() -> bool:
    """Check whether GitHub auth is available for Copilot SDK."""
    if get_github_token():
        return True
    try:
        result = subprocess.run(  # noqa: S603
            ["gh", "auth", "status", "--hostname", "github.com"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _check_github_auth():
    """Verify GitHub auth is available for Copilot integration tests."""
    if not _has_github_auth():
        pytest.skip(
            "GitHub auth required for Copilot integration tests. "
            "Set GITHUB_TOKEN or GH_TOKEN, or run `gh auth login --hostname github.com`."
        )
