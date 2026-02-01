"""Result models for pytest-aitest.

This module provides backwards-compatible imports from the new package structure.
New code should import from pytest_aitest.core directly.
"""

# Re-export from core module for backwards compatibility
from pytest_aitest.core.result import AgentResult, ToolCall, Turn

__all__ = [
    "AgentResult",
    "ToolCall",
    "Turn",
]
