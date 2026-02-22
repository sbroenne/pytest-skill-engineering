"""Pytest fixtures for pytest-aitest.

This module re-exports all fixtures for pytest plugin registration.
"""

# Re-export fixtures for pytest plugin discovery
from pytest_aitest.fixtures.factories import skill_factory
from pytest_aitest.fixtures.iteration import _aitest_iteration
from pytest_aitest.fixtures.llm_assert import llm_assert
from pytest_aitest.fixtures.llm_assert_image import llm_assert_image
from pytest_aitest.fixtures.llm_score import llm_score
from pytest_aitest.fixtures.run import _aitest_auto_cleanup, aitest_run

__all__ = [
    "_aitest_auto_cleanup",
    "_aitest_iteration",
    "aitest_run",
    "llm_assert",
    "llm_assert_image",
    "llm_score",
    "skill_factory",
]

# Conditionally register copilot fixtures when the SDK is available
try:
    from pytest_aitest.copilot.fixtures import ab_run, copilot_run  # noqa: F401

    __all__ += ["copilot_run", "ab_run"]
except ImportError:
    pass  # github-copilot-sdk not installed — copilot fixtures not available
