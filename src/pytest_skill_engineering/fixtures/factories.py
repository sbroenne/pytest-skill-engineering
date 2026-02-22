"""Factory fixtures for pytest-skill-engineering."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pytest_skill_engineering.core.skill import Skill


@pytest.fixture
def skill_factory() -> Callable[[Path | str], Skill]:
    """Factory fixture for loading Skills.

    Example:
        def test_with_skill(skill_factory, aitest_run):
            skill = skill_factory("path/to/my-skill")
            agent = Agent(
                provider=Provider(model="azure/gpt-5-mini"),
                skill=skill,
            )
            result = await aitest_run(agent, "Do something with the skill")
            assert result.success

        def test_skill_metadata(skill_factory):
            skill = skill_factory("skills/my-skill")
            assert skill.name == "my-skill"
            assert skill.has_references
    """

    def load(path: Path | str) -> Skill:
        """Load a Skill from a path.

        Args:
            path: Path to skill directory or SKILL.md file

        Returns:
            Loaded Skill instance
        """
        return Skill.from_path(path)

    return load
