"""Shared fixtures and constants for Copilot integration tests."""

from __future__ import annotations

import os
import subprocess

import pytest

# Default model — None means Copilot picks its default
DEFAULT_MODEL: str | None = None

# Models for parametrized tests
MODELS: list[str] = ["gpt-5.2", "claude-sonnet-4.6"]

# Timeouts
DEFAULT_TIMEOUT_S: float = 300.0

# Turn limits
DEFAULT_MAX_TURNS: int = 25


def _has_github_auth() -> bool:
    """Check whether GitHub auth is available for Copilot SDK."""
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


@pytest.fixture(scope="session", autouse=True)
def _check_github_auth():
    """Verify GitHub auth is available for Copilot integration tests."""
    if not _has_github_auth():
        pytest.skip(
            "GitHub auth required for Copilot integration tests. "
            "Set GITHUB_TOKEN or run `gh auth login`."
        )
