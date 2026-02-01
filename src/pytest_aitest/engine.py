"""Agent execution engine for pytest-aitest.

This module provides backwards-compatible imports from the new package structure.
New code should import from pytest_aitest.execution directly.
"""

# Re-export from execution module for backwards compatibility
from pytest_aitest.execution.engine import AgentEngine

__all__ = [
    "AgentEngine",
]
