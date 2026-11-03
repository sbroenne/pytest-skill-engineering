"""Pytest fixtures for pytest-copilot.

This module re-exports all fixtures for pytest plugin registration.
"""

# Re-export fixtures for pytest plugin discovery
from pytest_copilot.fixtures.factories import skill_factory
from pytest_copilot.fixtures.iteration import _aitest_iteration

__all__ = [
    "_aitest_iteration",
    "skill_factory",
]

# Copilot fixtures (required - no longer optional)
from pytest_copilot.copilot.fixtures import ab_run, copilot_run  # noqa: F401

__all__ += ["copilot_run", "ab_run"]
