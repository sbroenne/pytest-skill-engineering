"""Plugin loading infrastructure for testing plugin directories.

A "plugin" is a directory with a ``plugin.json`` manifest that bundles
custom agents, skills, MCP servers, hooks, instructions, and extensions.
Both GitHub Copilot CLI and Claude Code use this format (with minor differences).

Supports three directory layouts:

1. **Standalone plugin** — directory with ``plugin.json`` at root.
2. **GitHub Copilot project** — ``.github/`` directory with ``agents/``,
   ``copilot-instructions.md``, etc.
3. **Claude Code project** — ``.claude/`` directory with ``agents/``,
   ``CLAUDE.md``, ``commands/``, etc.

Example::

    from pytest_skill_engineering.core.plugin import load_plugin

    plugin = load_plugin("my-plugin/")
    # → Plugin(metadata=PluginMetadata(name="my-plugin"), ...)

    # Use with Eval.from_plugin()
    from pytest_skill_engineering import Eval, Provider
    agent = Eval.from_plugin(
        "my-plugin/",
        provider=Provider(model="azure/gpt-5-mini"),
    )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pytest_skill_engineering.core.skill import Skill

_logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class HookDefinition:
    """A lifecycle hook from a plugin's hooks configuration.

    Hooks allow plugins to execute shell commands at specific lifecycle events.

    Example ``hooks.json``::

        [
            {
                "event": "tool.execution_complete",
                "command": "npm run lint",
                "pattern": "*.ts"
            }
        ]
    """

    event: str  # e.g., "tool.execution_complete", "session.start"
    command: str  # Shell command to execute
    pattern: str = ""  # Optional file pattern filter


@dataclass(slots=True, frozen=True)
class PluginMetadata:
    """Plugin manifest metadata.

    Extracted from ``plugin.json`` or inferred from the directory name.
    """

    name: str
    version: str = ""
    description: str = ""
    author: str = ""


@dataclass(slots=True, frozen=True)
class Plugin:
    """A loaded plugin with all its components resolved.

    Created by :func:`load_plugin`. Contains everything discovered from
    the plugin directory: agents, skills, MCP servers, hooks, instructions,
    and extensions.
    """

    metadata: PluginMetadata
    path: Path
    agents: list[dict[str, Any]] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    hooks: list[HookDefinition] = field(default_factory=list)
    instructions: str = ""
    extensions: list[Path] = field(default_factory=list)


def load_plugin(path: str | Path) -> Plugin:
    """Load a plugin from a directory containing plugin.json.

    Supports both GitHub Copilot CLI and Claude Code plugin formats.
    Discovers and loads: custom agents, skills, MCP servers, hooks,
    instructions, and extensions.

    For ``.github/`` directories, discovers agents from ``agents/`` and
    instructions from ``copilot-instructions.md``.

    For ``.claude/`` directories, discovers agents from ``agents/`` and
    instructions from ``CLAUDE.md``.

    Args:
        path: Path to the plugin directory (must contain plugin.json,
            or be a ``.github/`` / ``.claude/`` project config directory)

    Returns:
        Plugin with all components resolved

    Raises:
        FileNotFoundError: If plugin.json doesn't exist (for non-project dirs)
        ValueError: If plugin.json is invalid
    """
    path = Path(path).resolve()

    if not path.is_dir():
        msg = f"Plugin path is not a directory: {path}"
        raise FileNotFoundError(msg)

    # Standard plugin with plugin.json (check first — plugins may also have agents/)
    manifest_path = path / "plugin.json"
    if manifest_path.exists():
        return _load_from_manifest(path, manifest_path)

    # Detect project config directories (no plugin.json)
    dir_name = path.name
    if dir_name == ".github":
        return _load_project_directory(path, format_hint="github")
    if dir_name == ".claude":
        return _load_project_directory(path, format_hint="claude")
    # Claude Code project root: has CLAUDE.md or .claude/ subdirectory
    if (path / "CLAUDE.md").exists() or (path / ".claude").is_dir():
        return _load_project_directory(path, format_hint="claude")
    # GitHub project root: has .github/agents/
    github_dir = path / ".github"
    if github_dir.is_dir() and (github_dir / "agents").is_dir():
        return _load_project_directory(github_dir, format_hint="github")

    msg = f"No plugin.json, CLAUDE.md, .claude/, or .github/agents/ found in: {path}"
    raise FileNotFoundError(msg)


def _load_from_manifest(path: Path, manifest_path: Path) -> Plugin:
    """Load a plugin from a plugin.json manifest."""
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"Invalid plugin.json in {path}: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(manifest, dict):
        msg = f"plugin.json must be a JSON object, got {type(manifest).__name__}"
        raise ValueError(msg)

    # Parse metadata
    metadata = _parse_metadata(manifest, fallback_name=path.name)

    # Discover agents
    agents = _discover_agents(path)

    # Discover skills
    skills = _discover_skills(path)

    # Parse MCP servers from manifest
    mcp_servers = _parse_mcp_servers(manifest)

    # Parse hooks
    hooks = _parse_hooks(path, manifest)

    # Discover instructions
    instructions = _discover_instructions(path, manifest)

    # Discover extensions
    extensions = _discover_extensions(path)

    return Plugin(
        metadata=metadata,
        path=path,
        agents=agents,
        skills=skills,
        mcp_servers=mcp_servers,
        hooks=hooks,
        instructions=instructions,
        extensions=extensions,
    )


def _has_agent_md_files(agents_dir: Path) -> bool:
    """Check if directory contains .agent.md or .md agent files."""
    if not agents_dir.is_dir():
        return False
    return any(agents_dir.glob("*.agent.md")) or any(
        p for p in agents_dir.glob("*.md") if not p.name.endswith(".agent.md")
    )


def _load_project_directory(path: Path, *, format_hint: str) -> Plugin:
    """Load from a project root or .github/.claude config directory."""
    metadata = PluginMetadata(name=path.name)

    agents: list[dict[str, Any]] = []
    skills: list[Skill] = []
    extensions: list[Path] = []
    mcp_servers: dict[str, dict[str, Any]] = {}
    instruction_parts: list[str] = []

    if format_hint == "claude":
        # Claude Code: check root and .claude/ subdirectory
        claude_dir = path / ".claude" if (path / ".claude").is_dir() else path
        agents = _discover_agents(claude_dir)
        skills = _discover_skills(claude_dir)
        # Instructions from CLAUDE.md at root and .claude/
        _append_file_content(instruction_parts, path / "CLAUDE.md")
        if claude_dir != path:
            _append_file_content(instruction_parts, claude_dir / "CLAUDE.md")
        # MCP servers from .mcp.json
        mcp_json = path / ".mcp.json"
        if mcp_json.exists():
            try:
                raw = json.loads(mcp_json.read_text(encoding="utf-8"))
                mcp_servers = raw.get("mcpServers", raw.get("mcp_servers", {}))
            except (json.JSONDecodeError, AttributeError):
                pass
    elif format_hint == "github":
        agents = _discover_agents(path)
        skills = _discover_skills(path)
        extensions = _discover_extensions(path)
        _append_file_content(instruction_parts, path / "copilot-instructions.md")
        _append_file_content(instruction_parts, path.parent / "copilot-instructions.md")

    instructions = "\n\n".join(instruction_parts)

    return Plugin(
        metadata=metadata,
        path=path,
        agents=agents,
        skills=skills,
        mcp_servers=mcp_servers,
        hooks=[],
        instructions=instructions,
        extensions=extensions,
    )


def _append_file_content(parts: list[str], file_path: Path) -> None:
    """Append file content to parts list if file exists and is non-empty."""
    if file_path.is_file():
        content = file_path.read_text(encoding="utf-8").strip()
        if content:
            parts.append(content)


def _parse_metadata(manifest: dict[str, Any], *, fallback_name: str) -> PluginMetadata:
    """Extract metadata from plugin.json manifest."""
    return PluginMetadata(
        name=str(manifest.get("name", fallback_name)),
        version=str(manifest.get("version", "")),
        description=str(manifest.get("description", "")),
        author=str(manifest.get("author", "")),
    )


def _discover_agents(plugin_dir: Path) -> list[dict[str, Any]]:
    """Discover and load custom agents from agents/ subdirectory."""
    from pytest_skill_engineering.core.evals import load_custom_agent  # noqa: PLC0415

    agents_dir = plugin_dir / "agents"
    if not agents_dir.is_dir():
        return []

    agents: list[dict[str, Any]] = []

    # Load .agent.md files (VS Code / Copilot format)
    for agent_file in sorted(agents_dir.glob("*.agent.md")):
        try:
            agents.append(load_custom_agent(agent_file))
        except (FileNotFoundError, ValueError) as exc:
            _logger.warning("Skipping agent file %s: %s", agent_file.name, exc)

    # Load plain .md files (Claude Code format) that aren't .agent.md
    seen_names = {a["name"] for a in agents}
    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.name.endswith(".agent.md"):
            continue
        try:
            agent = load_custom_agent(agent_file)
            if agent["name"] not in seen_names:
                agents.append(agent)
                seen_names.add(agent["name"])
        except (FileNotFoundError, ValueError) as exc:
            _logger.warning("Skipping agent file %s: %s", agent_file.name, exc)

    return agents


def _discover_skills(plugin_dir: Path) -> list[Skill]:
    """Discover and load skills from skills/ subdirectory."""
    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        return []

    skills: list[Skill] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            skills.append(Skill.from_path(skill_dir))
        except Exception as exc:
            _logger.warning("Skipping skill %s: %s", skill_dir.name, exc)

    return skills


def _parse_mcp_servers(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Parse MCP server configurations from plugin.json."""
    raw = manifest.get("mcp_servers", manifest.get("mcpServers", {}))
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _parse_hooks(plugin_dir: Path, manifest: dict[str, Any]) -> list[HookDefinition]:
    """Parse hooks from hooks.json or plugin.json hooks field."""
    hooks: list[HookDefinition] = []

    # Try hooks.json first
    hooks_file = plugin_dir / "hooks.json"
    if hooks_file.is_file():
        try:
            raw = json.loads(hooks_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for entry in raw:
                    hooks.append(_hook_from_dict(entry))
                return hooks
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            _logger.warning("Failed to parse hooks.json: %s", exc)

    # Fall back to plugin.json hooks field
    raw_hooks = manifest.get("hooks", [])
    if isinstance(raw_hooks, list):
        for entry in raw_hooks:
            try:
                hooks.append(_hook_from_dict(entry))
            except (KeyError, TypeError) as exc:
                _logger.warning("Skipping invalid hook entry: %s", exc)

    return hooks


def _hook_from_dict(data: Any) -> HookDefinition:
    """Create a HookDefinition from a dict."""
    if not isinstance(data, dict):
        msg = f"Hook entry must be a dict, got {type(data).__name__}"
        raise TypeError(msg)
    return HookDefinition(
        event=str(data["event"]),
        command=str(data["command"]),
        pattern=str(data.get("pattern", "")),
    )


def _discover_instructions(plugin_dir: Path, manifest: dict[str, Any]) -> str:
    """Discover and concatenate instruction content."""
    parts: list[str] = []

    # Well-known instruction files
    well_known = ["copilot-instructions.md", "CLAUDE.md"]
    for filename in well_known:
        _append_file_content(parts, plugin_dir / filename)

    # Files listed in plugin.json instructions field
    listed = manifest.get("instructions", [])
    if isinstance(listed, list):
        for entry in listed:
            filepath = plugin_dir / str(entry)
            _append_file_content(parts, filepath)
    elif isinstance(listed, str):
        _append_file_content(parts, plugin_dir / listed)

    return "\n\n".join(parts)


def _discover_extensions(plugin_dir: Path) -> list[Path]:
    """Discover extension.mjs files in extensions/ subdirectory."""
    ext_dir = plugin_dir / "extensions"
    if not ext_dir.is_dir():
        return []
    return sorted(ext_dir.glob("extension.mjs"))
