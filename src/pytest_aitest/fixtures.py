"""Pytest fixtures for pytest-aitest.

This module provides backwards-compatible imports from the new package structure.
New code should import from pytest_aitest.fixtures directly.
"""

# Re-export from fixtures package for backwards compatibility
from pytest_aitest.fixtures import (
    _aitest_auto_cleanup,
    agent_factory,
    aitest_run,
    judge,
    provider_factory,
    skill_factory,
)

__all__ = [
    "_aitest_auto_cleanup",
    "agent_factory",
    "aitest_run",
    "judge",
    "provider_factory",
    "skill_factory",
]
