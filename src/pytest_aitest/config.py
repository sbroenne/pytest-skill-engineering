"""Configuration models for pytest-aitest.

This module provides backwards-compatible imports from the new package structure.
New code should import from pytest_aitest.core directly.
"""

from __future__ import annotations

from dataclasses import dataclass

# Re-export from core module for backwards compatibility
from pytest_aitest.core.agent import (
    Agent,
    CLIServer,
    MCPServer,
    Provider,
    Wait,
    WaitStrategy,
)

__all__ = [
    "Agent",
    "CLIServer",
    "Judge",
    "MCPServer",
    "Provider",
    "Wait",
    "WaitStrategy",
]


@dataclass(slots=True)
class Judge:
    """LLM judge configuration for semantic assertions.

    Authentication is handled by LiteLLM via standard environment variables.
    See https://docs.litellm.ai/docs/providers for configuration.

    Example:
        Judge(model="openai/gpt-4o-mini")
    """

    model: str = "openai/gpt-4o-mini"
