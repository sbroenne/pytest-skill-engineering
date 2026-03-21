"""Pytest fixtures for pytest-skill-engineering.

This module re-exports all fixtures for pytest plugin registration.
"""

# Re-export fixtures for pytest plugin discovery
from pytest_skill_engineering.fixtures.factories import skill_factory
from pytest_skill_engineering.fixtures.iteration import _aitest_iteration
from pytest_skill_engineering.fixtures.llm_assert import llm_assert
from pytest_skill_engineering.fixtures.llm_assert_image import llm_assert_image
from pytest_skill_engineering.fixtures.llm_score import llm_score
from pytest_skill_engineering.fixtures.skill_eval import skill_eval_runner

__all__ = [
    "_aitest_iteration",
    "llm_assert",
    "llm_assert_image",
    "llm_score",
    "skill_eval_runner",
    "skill_factory",
]

# Copilot fixtures (required - no longer optional)
from pytest_skill_engineering.copilot.fixtures import ab_run, copilot_eval  # noqa: F401

__all__ += ["copilot_eval", "ab_run"]
