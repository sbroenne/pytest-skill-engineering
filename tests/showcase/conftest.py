"""Shared configuration for the showcase test suite."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from tests.integration.conftest import BANKING_PROMPT


@pytest.fixture
def banking_mcp_servers() -> dict[str, dict[str, Any]]:
    """Configure the built-in banking MCP server for Copilot sessions."""
    return {
        "banking": {
            "command": sys.executable,
            "args": ["-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
            "tools": ["*"],
        }
    }


@pytest.fixture
def banking_system_prompt() -> str:
    """Return the shared banking system prompt."""
    return BANKING_PROMPT
