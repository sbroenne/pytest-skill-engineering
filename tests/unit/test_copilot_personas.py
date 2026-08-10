"""Unit tests for persona skill reference polyfills.

Tests that _inject_skill_reference_tools correctly scans skill directories
and injects list_skill_references/read_skill_reference tools.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.copilot.contracts import CopilotEvalConfig
from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.events import EventMapper
from pytest_skill_engineering.copilot.personas import (
    ClaudeCodePersona,
    CopilotCLIPersona,
    VSCodePersona,
    _inject_skill_reference_tools,
)
from pytest_skill_engineering.copilot.result import CopilotResult


async def _unused_nested_runner(agent: CopilotEvalConfig, prompt: str) -> CopilotResult:
    raise AssertionError(f"Unexpected nested run for {agent.name}: {prompt}")


@pytest.fixture()
def skill_dir(tmp_path: Path) -> Path:
    """Create a skill directory with SKILL.md and references/."""
    skill = tmp_path / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: my-skill\n---\n# My Skill\nInstructions here.")
    refs = skill / "references"
    refs.mkdir()
    (refs / "guide.md").write_text("# Guide\nDetailed info.")
    (refs / "lookup.txt").write_text("key1=value1\nkey2=value2")
    (refs / "data.json").write_text('{"items": [1, 2, 3]}')
    # Non-matching file extension should be ignored
    (refs / "image.png").write_bytes(b"\x89PNG")
    return skill


@pytest.fixture()
def skill_dir_no_refs(tmp_path: Path) -> Path:
    """Create a skill directory without references/."""
    skill = tmp_path / "no-refs-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: no-refs\n---\n# No Refs")
    return skill


class TestInjectSkillReferenceTools:
    """Test _inject_skill_reference_tools directly."""

    def test_no_skill_directories(self) -> None:
        """No-op when agent has no skill_directories."""
        agent = CopilotEval(skill_directories=[])
        config: dict = {}
        _inject_skill_reference_tools(agent, config)
        assert "tools" not in config

    def test_skill_without_references_no_tools(self, skill_dir_no_refs: Path) -> None:
        """No tools injected when skill has no references/ dir."""
        agent = CopilotEval(skill_directories=[str(skill_dir_no_refs)])
        config: dict = {}
        _inject_skill_reference_tools(agent, config)
        assert "tools" not in config

    def test_skill_with_references_injects_tools(self, skill_dir: Path) -> None:
        """Two tools injected when skill has references/."""
        agent = CopilotEval(skill_directories=[str(skill_dir)])
        config: dict = {}
        _inject_skill_reference_tools(agent, config)
        assert "tools" in config
        tool_names = [t.name for t in config["tools"]]
        assert "list_skill_references" in tool_names
        assert "read_skill_reference" in tool_names

    def test_only_supported_extensions(self, skill_dir: Path) -> None:
        """Only .md, .txt, .json, .yaml, .yml files are included."""
        agent = CopilotEval(skill_directories=[str(skill_dir)])
        config: dict = {}
        _inject_skill_reference_tools(agent, config)
        read_tool = next(t for t in config["tools"] if t.name == "read_skill_reference")
        enum_values = read_tool.parameters["properties"]["filename"]["enum"]
        assert "guide.md" in enum_values
        assert "lookup.txt" in enum_values
        assert "data.json" in enum_values
        assert "image.png" not in enum_values

    def test_system_message_added(self, skill_dir: Path) -> None:
        """System message mentioning references is prepended."""
        agent = CopilotEval(skill_directories=[str(skill_dir)])
        config: dict = {}
        _inject_skill_reference_tools(agent, config)
        assert "system_message" in config
        content = config["system_message"]["content"]
        assert "list_skill_references" in content
        assert "read_skill_reference" in content

    def test_parent_directory_scanning(self, tmp_path: Path) -> None:
        """When skill_directories points to parent, scans subdirectories."""
        parent = tmp_path / "skills"
        parent.mkdir()
        skill = parent / "child-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: child\n---\n# Child")
        refs = skill / "references"
        refs.mkdir()
        (refs / "doc.md").write_text("# Doc")

        agent = CopilotEval(skill_directories=[str(parent)])
        config: dict = {}
        _inject_skill_reference_tools(agent, config)
        assert "tools" in config
        read_tool = next(t for t in config["tools"] if t.name == "read_skill_reference")
        assert "doc.md" in read_tool.parameters["properties"]["filename"]["enum"]


class TestPersonaSkillRefIntegration:
    """Test that each persona calls _inject_skill_reference_tools."""

    def _make_agent(self, skill_dir: Path) -> CopilotEval:
        return CopilotEval(
            skill_directories=[str(skill_dir)],
        )

    def test_vscode_persona_injects_refs(self, skill_dir: Path) -> None:
        persona = VSCodePersona()
        agent = self._make_agent(skill_dir)
        config: dict = {}
        mapper = EventMapper()
        persona.apply(agent, config, mapper, _unused_nested_runner)
        tool_names = [t.name for t in config.get("tools", [])]
        assert "list_skill_references" in tool_names

    def test_copilot_cli_persona_injects_refs(self, skill_dir: Path) -> None:
        persona = CopilotCLIPersona()
        agent = self._make_agent(skill_dir)
        config: dict = {}
        mapper = EventMapper()
        persona.apply(agent, config, mapper, _unused_nested_runner)
        tool_names = [t.name for t in config.get("tools", [])]
        assert "list_skill_references" in tool_names

    def test_claude_code_persona_injects_refs(self, skill_dir: Path) -> None:
        persona = ClaudeCodePersona()
        agent = self._make_agent(skill_dir)
        config: dict = {}
        mapper = EventMapper()
        persona.apply(agent, config, mapper, _unused_nested_runner)
        tool_names = [t.name for t in config.get("tools", [])]
        assert "list_skill_references" in tool_names
