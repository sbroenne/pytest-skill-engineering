"""Strict configuration errors and a real Copilot workflow using validated config."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from pytest_skill_engineering import Skill, load_custom_agent, load_plugin
from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.copilot.config import load_mcp_config
from pytest_skill_engineering.core.evals import (
    load_custom_agents,
    load_instruction_file,
    load_instruction_files,
    load_prompt_file,
    load_prompt_files,
)
from pytest_skill_engineering.core.skill import SkillError

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot]


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _manifest(root: Path, **fields: Any) -> Path:
    return _write(root / "plugin.json", json.dumps({"name": "validation-plugin", **fields}))


@pytest.mark.parametrize(
    "content",
    [
        "---\ndescription: [broken\n---\nDo the work.",
        "---\ndescription: unfinished\nDo the work.",
        "---\n- not a mapping\n---\nDo the work.",
        "---\nnull\n---\nDo the work.",
        "---\nname: 123\n---\nDo the work.",
        "---\ndescription: []\n---\nDo the work.",
        "---\ntools: {not: a-list}\n---\nDo the work.",
        "---\ndescription: Valid metadata\n---\n ",
    ],
)
def test_invalid_custom_agent_stops_discovery(tmp_path: Path, content: str) -> None:
    """Invalid custom agents fail both direct and directory/plugin loading."""
    _manifest(tmp_path)
    agent = _write(tmp_path / "agents" / "broken.agent.md", content)
    for loader, path in (
        (load_custom_agent, agent),
        (load_custom_agents, agent.parent),
        (load_plugin, tmp_path),
    ):
        with pytest.raises(ValueError, match=re.escape(str(agent))):
            loader(path)


@pytest.mark.parametrize("suffix", [".prompt.md", ".md", ".instructions.md"])
def test_invalid_instruction_and_prompt_files_are_not_skipped(tmp_path: Path, suffix: str) -> None:
    """Malformed frontmatter and empty discovered files never become empty success."""
    target = _write(tmp_path / f"broken{suffix}", "---\napplyTo: [broken\n---\nBody")
    loaders = (
        (load_instruction_file, load_instruction_files)
        if suffix == ".instructions.md"
        else (load_prompt_file, load_prompt_files)
    )
    for content in ("---\napplyTo: [broken\n---\nBody", " "):
        target.write_text(content, encoding="utf-8")
        for loader, path in ((loaders[0], target), (loaders[1], tmp_path)):
            with pytest.raises(ValueError, match=re.escape(str(target))):
                loader(path)


@pytest.mark.parametrize(
    "metadata",
    [
        "name: sample",
        "description: Missing name",
        "name: 42\ndescription: Invalid name type",
        "name: sample\ndescription: true",
        "name: sample\ndescription: ' '",
        "name: sample\ndescription: Valid\nallowed-tools: 123",
        "name: sample\ndescription: Valid\ntags: {}",
        "name: sample\ndescription: Valid\nmetadata: []",
        "name: [broken",
    ],
)
def test_invalid_skill_stops_plugin_loading(tmp_path: Path, metadata: str) -> None:
    """Missing or malformed skill metadata is reported with its SKILL.md path."""
    _manifest(tmp_path)
    skill = _write(tmp_path / "skills" / "sample" / "SKILL.md", f"---\n{metadata}\n---\nBody")
    with pytest.raises(SkillError, match=re.escape(str(skill))):
        Skill.from_path(skill)
    with pytest.raises(SkillError, match=re.escape(str(skill))):
        load_plugin(tmp_path)


def test_missing_or_empty_skill_definition_is_an_error(tmp_path: Path) -> None:
    """A discovered skill directory must have a complete definition."""
    _manifest(tmp_path)
    skill = tmp_path / "skills" / "sample" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    with pytest.raises(SkillError, match=re.escape(str(skill))):
        load_plugin(tmp_path)
    _write(skill, "---\nname: sample\ndescription: Valid\n---\n")
    with pytest.raises(SkillError, match=re.escape(str(skill))):
        load_plugin(tmp_path)


@pytest.mark.parametrize("component", ["references", "scripts", "assets"])
def test_invalid_skill_component_paths_fail(tmp_path: Path, component: str) -> None:
    skill = _write(
        tmp_path / "sample" / "SKILL.md",
        "---\nname: sample\ndescription: Valid skill\n---\nUse the tools.",
    )
    invalid = _write(skill.parent / component, "Not a directory")
    with pytest.raises(SkillError, match=re.escape(str(invalid))):
        Skill.from_path(skill)


def test_duplicate_instruction_names_cannot_hide_invalid_files(tmp_path: Path) -> None:
    _write(tmp_path / "AGENTS.instructions.md", "Valid scoped instructions.")
    invalid = _write(tmp_path / "AGENTS.md", "---\napplyTo: [broken\n---\nBody")
    with pytest.raises(ValueError, match=re.escape(str(invalid))):
        load_instruction_files(tmp_path)


@pytest.mark.parametrize("key", ["mcpServers", "mcp_servers"])
@pytest.mark.parametrize(
    "servers",
    [
        [],
        None,
        {"broken": None},
        {"broken": {}},
        {"broken": {"command": 123}},
        {"broken": {"command": "python", "args": "not-a-list"}},
        {"broken": {"command": "python", "env": {"PORT": 123}}},
        {"broken": {"url": ""}},
        {"broken": {"url": "not-a-url"}},
        {"broken": {"url": "https://example.com", "headers": []}},
        {"broken": {"type": "http", "command": "python"}},
        {"broken": {"type": "unknown", "command": "python"}},
        {"broken": {"command": "python", "url": "https://example.com"}},
    ],
)
def test_invalid_mcp_payload_is_an_error(tmp_path: Path, key: str, servers: Any) -> None:
    """Both supported MCP field spellings reject invalid payloads and entries."""
    manifest = _manifest(tmp_path, **{key: servers})
    with pytest.raises(ValueError, match=re.escape(str(manifest))):
        load_plugin(tmp_path)
    claude = tmp_path / ".claude"
    claude.mkdir()
    mcp = _write(claude / ".mcp.json", json.dumps({key: servers}))
    with pytest.raises(ValueError, match=re.escape(str(mcp))):
        load_plugin(claude)


@pytest.mark.parametrize("content", ["{broken", "[]", "null", "{}"])
def test_invalid_claude_mcp_file_does_not_become_empty_config(tmp_path: Path, content: str) -> None:
    """An existing .mcp.json must contain a valid explicit server mapping."""
    claude = tmp_path / ".claude"
    mcp = _write(claude / ".mcp.json", content)
    with pytest.raises(ValueError, match=re.escape(str(mcp))):
        load_plugin(claude)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"mcpServers": None},
        {"servers": []},
        {"mcpServers": [], "servers": {}},
        {"mcpServers": {}, "servers": []},
        {"mcpServers": {}, "servers": {}},
        {"mcpServers": {"broken": {}}},
        {"servers": {"broken": {"command": 123}}},
    ],
)
def test_invalid_standalone_mcp_config_fails(tmp_path: Path, payload: Any) -> None:
    """Invalid explicit keys cannot be hidden by another supported key."""
    source = _write(tmp_path / "mcp.json", json.dumps(payload))
    with pytest.raises(ValueError, match=re.escape(str(source))):
        load_mcp_config(source)


@pytest.mark.parametrize("key", ["mcpServers", "servers"])
def test_standalone_mcp_formats_preserve_valid_mappings(tmp_path: Path, key: str) -> None:
    servers = {"banking": {"command": "python", "args": ["-m", "banking"]}}
    source = _write(tmp_path / "mcp.json", json.dumps({key: servers}))
    assert load_mcp_config(source) == servers
    _write(source, json.dumps({key: {}}))
    assert load_mcp_config(source) == {}


@pytest.mark.parametrize(
    "hooks",
    [
        {},
        None,
        [None],
        [{"event": "session.start"}],
        [{"command": "echo valid"}],
        [{"event": 123, "command": "echo valid"}],
        [{"event": "session.start", "command": " "}],
        [{"event": "session.start", "command": "echo valid", "pattern": []}],
    ],
)
def test_invalid_hooks_fail_without_partial_results(tmp_path: Path, hooks: Any) -> None:
    """Bad hooks fail instead of being skipped or replaced by another source."""
    manifest = _manifest(tmp_path, hooks=hooks)
    with pytest.raises(ValueError, match=re.escape(str(manifest))):
        load_plugin(tmp_path)
    _manifest(tmp_path, hooks=[{"event": "session.start", "command": "echo valid"}])
    hook_file = _write(tmp_path / "hooks.json", json.dumps(hooks))
    with pytest.raises(ValueError, match=re.escape(str(hook_file))):
        load_plugin(tmp_path)
    hook_file.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(str(hook_file))):
        load_plugin(tmp_path)


@pytest.mark.parametrize("instructions", [None, {}, 123, [None], [""]])
def test_invalid_instruction_reference_types_fail(tmp_path: Path, instructions: Any) -> None:
    manifest = _manifest(tmp_path, instructions=instructions)
    with pytest.raises(ValueError, match=re.escape(str(manifest))):
        load_plugin(tmp_path)


def test_explicit_instruction_reference_is_required(tmp_path: Path) -> None:
    """Optional absence is valid, but explicit missing or empty instructions are not."""
    _manifest(tmp_path)
    assert load_plugin(tmp_path).instructions == ""
    target = tmp_path / "required.md"
    _manifest(tmp_path, instructions=target.name)
    with pytest.raises(FileNotFoundError, match=re.escape(str(target))):
        load_plugin(tmp_path)
    _write(target, "")
    with pytest.raises(ValueError, match=re.escape(str(target))):
        load_plugin(tmp_path)
    _write(target, "---\napplyTo: []\n---\nDo the work.")
    with pytest.raises(ValueError, match=re.escape(str(target))):
        load_plugin(tmp_path)


@pytest.mark.parametrize("filename", ["copilot-instructions.md", "CLAUDE.md"])
def test_present_optional_instructions_are_validated(tmp_path: Path, filename: str) -> None:
    _manifest(tmp_path)
    target = _write(tmp_path / filename, "")
    with pytest.raises(ValueError, match=re.escape(str(target))):
        load_plugin(tmp_path)


@pytest.mark.parametrize("key", ["mcp_servers", "mcpServers"])
def test_valid_mcp_transports_and_hooks_are_preserved(tmp_path: Path, key: str) -> None:
    servers = {
        "local": {"command": "python", "args": [], "env": {"MODE": "test"}},
        "remote": {"type": "http", "url": "https://example.com/mcp", "tools": ["*"]},
    }
    _manifest(
        tmp_path,
        hooks=[{"event": "session.start", "command": "echo configured", "pattern": ""}],
        **{key: servers},
    )
    plugin = load_plugin(tmp_path)
    assert plugin.mcp_servers == servers
    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].command == "echo configured"
    assert plugin.hooks[0].pattern == ""


@pytest.mark.parametrize("metadata", [{}, {"name": None}, {"name": 123}, {"name": " "}])
def test_manifest_requires_explicit_name(tmp_path: Path, metadata: dict[str, Any]) -> None:
    manifest = _write(tmp_path / "plugin.json", json.dumps(metadata))
    with pytest.raises(ValueError, match=re.escape(str(manifest))):
        load_plugin(tmp_path)


@pytest.mark.parametrize("directory", [".github", ".claude"])
def test_absent_optional_project_components_remain_valid(tmp_path: Path, directory: str) -> None:
    root = tmp_path / directory
    root.mkdir()
    plugin = load_plugin(root)
    assert plugin.metadata.name == directory
    assert plugin.agents == []
    assert plugin.skills == []
    assert plugin.mcp_servers == {}
    assert plugin.hooks == []
    assert plugin.instructions == ""


@pytest.mark.parametrize("suffix", [".agent.md", ".md"])
def test_filename_derived_names_and_optional_frontmatter(tmp_path: Path, suffix: str) -> None:
    agent = _write(tmp_path / f"helper{suffix}", "Use the available tools to help.")
    assert load_custom_agent(agent)["name"] == "helper"
    agent.write_text("---\ndescription: Helpful specialist\n---\nUse tools.", encoding="utf-8")
    assert load_custom_agent(agent)["name"] == "helper"


@pytest.mark.parametrize("format_name", ["copilot", "claude"])
@pytest.mark.parametrize(
    "content",
    [
        "---\ndescription: [broken\n---\nBody",
        "---\ndescription: Missing delimiter",
        "---\n- not a mapping\n---\nBody",
        "---\nname: 123\n---\nBody",
        "",
    ],
)
def test_project_factories_reject_invalid_custom_agents(
    tmp_path: Path, format_name: str, content: str
) -> None:
    directory = ".github" if format_name == "copilot" else ".claude"
    suffix = ".agent.md" if format_name == "copilot" else ".md"
    target = _write(tmp_path / directory / "agents" / f"broken{suffix}", content)
    factory = (
        CopilotEval.from_copilot_config
        if format_name == "copilot"
        else CopilotEval.from_claude_config
    )
    with pytest.raises(ValueError, match=re.escape(str(target))):
        factory(tmp_path, model=DEFAULT_MODEL)


@pytest.mark.parametrize("format_name", ["copilot", "claude"])
def test_project_factories_validate_present_instructions(tmp_path: Path, format_name: str) -> None:
    target = (
        tmp_path / ".github" / "copilot-instructions.md"
        if format_name == "copilot"
        else tmp_path / "CLAUDE.md"
    )
    factory = (
        CopilotEval.from_copilot_config
        if format_name == "copilot"
        else CopilotEval.from_claude_config
    )
    for content in ("", "---\napplyTo: [broken\n---\nBody"):
        _write(target, content)
        with pytest.raises(ValueError, match=re.escape(str(target))):
            factory(tmp_path, model=DEFAULT_MODEL)


@pytest.mark.parametrize("content", ["{broken", "{}", '{"mcpServers": []}'])
def test_claude_factory_rejects_invalid_mcp(tmp_path: Path, content: str) -> None:
    target = _write(tmp_path / ".mcp.json", content)
    with pytest.raises(ValueError, match=re.escape(str(target))):
        CopilotEval.from_claude_config(tmp_path, model=DEFAULT_MODEL)


def test_claude_factory_validates_discovered_skills(tmp_path: Path) -> None:
    target = _write(
        tmp_path / ".claude" / "skills" / "broken" / "SKILL.md",
        "---\nname: broken\ndescription: 123\n---\nBody",
    )
    with pytest.raises(SkillError, match=re.escape(str(target))):
        CopilotEval.from_claude_config(tmp_path, model=DEFAULT_MODEL)


@pytest.mark.parametrize("format_name", ["copilot", "claude"])
def test_project_factories_preserve_optional_absence_and_agent_names(
    tmp_path: Path, format_name: str
) -> None:
    directory = ".github" if format_name == "copilot" else ".claude"
    suffix = ".agent.md" if format_name == "copilot" else ".md"
    factory = (
        CopilotEval.from_copilot_config
        if format_name == "copilot"
        else CopilotEval.from_claude_config
    )
    assert factory(tmp_path, model=DEFAULT_MODEL).custom_agents == []
    target = _write(
        tmp_path / directory / "agents" / f"helper{suffix}",
        "Use the tools to help.",
    )
    loaded = factory(tmp_path, model=DEFAULT_MODEL)
    assert loaded.custom_agents[0].get("name") == "helper"
    assert loaded.custom_agents[0].get("prompt") == "Use the tools to help."
    _write(target, "---\nname: explicit-name\n---\nUse tools.")
    assert factory(tmp_path, model=DEFAULT_MODEL).custom_agents[0].get("name") == "explicit-name"


@pytest.mark.parametrize("format_name", ["copilot", "claude"])
async def test_validated_plugin_runs_real_banking_workflow(
    copilot_eval: Any, tmp_path: Path, format_name: str
) -> None:
    """Valid Copilot/Claude definitions still execute a real MCP banking tool."""
    root = tmp_path / format_name
    suffix = ".agent.md" if format_name == "copilot" else ".md"
    key = "mcp_servers" if format_name == "copilot" else "mcpServers"
    _manifest(
        root,
        instructions="banking.md",
        **{
            key: {
                "banking": {
                    "command": sys.executable,
                    "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
                    "tools": ["*"],
                }
            }
        },
    )
    _write(
        root / "banking.md",
        "Use banking MCP tools for every balance request. Never invent account balances.",
    )
    _write(
        root / "agents" / f"banking-helper{suffix}",
        "---\ndescription: Banking specialist\n---\nUse banking tools to look up balances.",
    )
    _write(
        root / "skills" / "banking" / "SKILL.md",
        "---\nname: banking\ndescription: Accurate balance reporting\n---\n"
        "Use get_balance to retrieve current account balances.",
    )
    plugin = load_plugin(root)
    assert plugin.agents[0]["name"] == "banking-helper"
    assert plugin.skills[0].name == "banking"
    config_key = "servers" if format_name == "copilot" else "mcpServers"
    mcp_file = _write(root / "mcp.json", json.dumps({config_key: plugin.mcp_servers}))
    eval_config = CopilotEval.from_plugin(
        root,
        model=DEFAULT_MODEL,
        working_directory=str(root),
        mcp_servers=load_mcp_config(mcp_file),
        excluded_tools=["runSubagent", "task"],
    )
    result = await copilot_eval(
        eval_config,
        "Use the banking get_balance tool to get my checking balance, then report the amount.",
    )
    assert result.success, result.error
    assert any(
        re.search(r"(?:^|[_.:/-])get_balance$", name) for name in result.tool_names_called
    ), f"Expected a direct banking get_balance call; got {sorted(result.tool_names_called)}"
    assert re.search(r"(?<!\d)1500(?:\.0+)?(?![\d.])", result.final_response.replace(",", "")), (
        f"Expected the checking balance of 1500.0; got {result.final_response!r}"
    )
