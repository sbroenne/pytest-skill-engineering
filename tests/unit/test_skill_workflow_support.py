"""Deterministic coverage for skill workflow parsing and result helpers."""

from __future__ import annotations

from pathlib import Path

from pytest_skill_engineering.core.skill import Skill
from pytest_skill_engineering.core.skill_evals import has_skill_evals, load_skill_evals

PLUGIN_SKILL_DIR = (
    Path(__file__).parents[1]
    / "integration"
    / "plugins"
    / "banking-plugin"
    / "skills"
    / "financial-literacy"
)
MATH_SKILL_DIR = Path(__file__).parents[1] / "integration" / "skills" / "math-helper"


def test_plugin_skill_loads_from_plugin_directory() -> None:
    skill = Skill.from_path(PLUGIN_SKILL_DIR)
    assert skill.metadata.name == "financial-literacy"
    assert skill.metadata.description == "Domain knowledge for banking operations"
    assert "banking" in skill.metadata.tags


def test_plugin_skill_declares_evals() -> None:
    assert has_skill_evals(PLUGIN_SKILL_DIR)


def test_plugin_skill_evals_parse_with_expected_structure() -> None:
    cases = load_skill_evals(PLUGIN_SKILL_DIR)
    assert len(cases) == 2
    assert cases[0].prompt
    assert len(cases[0].expectations) == 3
    assert len(cases[1].expectations) == 2


def test_math_skill_evals_parse_with_expected_case_ids() -> None:
    cases = load_skill_evals(MATH_SKILL_DIR)
    assert [case.id for case in cases] == [1, 2]
    assert all(case.prompt for case in cases)
