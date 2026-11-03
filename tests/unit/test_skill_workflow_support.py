"""Deterministic coverage for skill workflow parsing and result helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pytest_copilot.copilot import CopilotTask
from pytest_copilot.core.plugin import load_plugin
from pytest_copilot.core.skill import Skill
from pytest_copilot.core.skill_evals import has_skill_evals, load_skill_evals

PLUGIN_SKILL_DIR = (
    Path(__file__).parents[1]
    / "integration"
    / "plugins"
    / "banking-plugin"
    / "skills"
    / "financial-literacy"
)
MATH_SKILL_DIR = Path(__file__).parents[1] / "integration" / "skills" / "math-helper"


def test_plugin_author_uses_current_project_name() -> None:
    plugin = load_plugin(PLUGIN_SKILL_DIR.parents[1])
    assert plugin.metadata.author == "pytest-copilot"


def test_claude_project_server_uses_installed_module() -> None:
    project = PLUGIN_SKILL_DIR.parents[2] / "claude-project"
    agent = CopilotTask.from_claude_config(project)
    server = agent.mcp_servers["banking"]
    assert server.get("command") == "python"
    assert server.get("args") == ["-m", "pytest_copilot.testing.banking_mcp"]
    assert importlib.util.find_spec("pytest_copilot.testing.banking_mcp") is not None


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
