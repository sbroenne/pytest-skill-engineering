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
    from pytest_skill_engineering.copilot.eval import CopilotEval

    plugin = load_plugin("my-plugin/")
    # → Plugin(metadata=PluginMetadata(name="my-plugin"), ...)

    agent = CopilotEval.from_plugin(
        "my-plugin/",
        model="gpt-5.4-mini",
    )
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pytest_skill_engineering.core.evals import load_custom_agent, load_instruction_file
from pytest_skill_engineering.core.skill import Skill


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
    manifest = _read_json(manifest_path)

    if not isinstance(manifest, dict):
        msg = f"{manifest_path}: must be a JSON object, got {type(manifest).__name__}"
        raise ValueError(msg)

    # Parse metadata
    metadata = _parse_metadata(manifest, manifest_path)

    # Discover agents
    agents = _discover_agents(path)

    # Discover skills
    skills = _discover_skills(path)
    _validate_skill_reference_names(skills)

    # Parse MCP servers from manifest
    mcp_servers = _parse_mcp_servers(manifest, manifest_path)

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
            mcp_servers = _load_claude_project_mcp_servers(mcp_json)
    elif format_hint == "github":
        agents = _discover_agents(path)
        skills = _discover_skills(path)
        extensions = _discover_extensions(path)
        _append_file_content(instruction_parts, path / "copilot-instructions.md")
        _append_file_content(instruction_parts, path.parent / "copilot-instructions.md")

    _validate_skill_reference_names(skills)
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


def _append_file_content(parts: list[str], file_path: Path, *, required: bool = False) -> None:
    """Load instructions, allowing absence only for conventionally discovered files."""
    if required or file_path.exists():
        parts.append(load_instruction_file(file_path)["content"])


def _string_field(
    data: dict[str, Any],
    field: str,
    source: Path,
    *,
    required: bool = False,
    allow_empty: bool = False,
) -> str:
    """Read a string field, distinguishing optional absence from invalid content."""
    if field not in data and not required:
        return ""
    value = data.get(field)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{source}: '{field}' must be a non-empty string")
    return value


def _parse_metadata(manifest: dict[str, Any], source: Path) -> PluginMetadata:
    """Extract metadata from plugin.json manifest."""
    return PluginMetadata(
        name=_string_field(manifest, "name", source, required=True),
        version=_string_field(manifest, "version", source),
        description=_string_field(manifest, "description", source),
        author=_string_field(manifest, "author", source),
    )


def _load_claude_project_mcp_servers(mcp_json: Path) -> dict[str, dict[str, Any]]:
    """Load MCP server definitions from a Claude project ``.mcp.json`` file."""
    raw = _read_json(mcp_json)

    if not isinstance(raw, dict):
        raise ValueError(f"{mcp_json}: must contain a JSON object")
    if "mcpServers" not in raw and "mcp_servers" not in raw:
        raise ValueError(f"{mcp_json}: missing MCP server mapping ('mcpServers' or 'mcp_servers')")

    return _parse_mcp_servers(raw, mcp_json)


def _read_json(path: Path) -> Any:
    """Decode configuration with a file-specific error for invalid JSON or UTF-8."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"{path}: Invalid JSON configuration: {exc}") from exc


def _discover_agents(plugin_dir: Path) -> list[dict[str, Any]]:
    """Discover and load custom agents from agents/ subdirectory."""
    agents_dir = plugin_dir / "agents"
    if not agents_dir.exists():
        return []
    if not agents_dir.is_dir():
        raise ValueError(f"{agents_dir}: custom agents path must be a directory")

    agents: list[dict[str, Any]] = []

    # Load .agent.md files (VS Code / Copilot format)
    for agent_file in sorted(agents_dir.glob("*.agent.md")):
        agents.append(load_custom_agent(agent_file))

    # Load plain .md files (Claude Code format) that aren't .agent.md
    seen_names = {a["name"] for a in agents}
    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.name.endswith(".agent.md"):
            continue
        agent = load_custom_agent(agent_file)
        if agent["name"] in seen_names:
            raise ValueError(f"{agent_file}: Duplicate custom agent name '{agent['name']}'")
        agents.append(agent)
        seen_names.add(agent["name"])

    return agents


def _discover_skills(plugin_dir: Path) -> list[Skill]:
    """Discover and load skills from skills/ subdirectory."""
    skills_dir = plugin_dir / "skills"
    if not skills_dir.exists():
        return []
    if not skills_dir.is_dir():
        raise ValueError(f"{skills_dir}: skills path must be a directory")

    skills: list[Skill] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skills.append(Skill.from_path(skill_dir))

    return skills


def _validate_skill_reference_names(skills: list[Skill]) -> None:
    """Reject duplicate reference basenames across loaded skills."""
    owners: dict[str, str] = {}
    for skill in skills:
        for reference_name in skill.references:
            owner = owners.get(reference_name)
            if owner is not None:
                msg = (
                    f"Duplicate skill reference filename '{reference_name}' in skills "
                    f"'{owner}' and '{skill.name}'. Reference filenames must be unique "
                    "across a loaded plugin so they cannot overwrite each other."
                )
                raise ValueError(msg)
            owners[reference_name] = skill.name


def _parse_mcp_servers(manifest: dict[str, Any], source: Path) -> dict[str, dict[str, Any]]:
    """Validate Copilot and Claude MCP mappings without discarding invalid entries."""
    fields = [field for field in ("mcp_servers", "mcpServers") if field in manifest]
    if not fields:
        return {}
    if len(fields) != 1:
        raise ValueError(f"{source}: specify only one of 'mcp_servers' and 'mcpServers'")
    return _validate_mcp_servers(manifest[fields[0]], source, field=fields[0])


def _validate_mcp_servers(raw: Any, source: Path, *, field: str) -> dict[str, dict[str, Any]]:
    """Validate the shared server mapping contract for plugin and MCP config files."""
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: '{field}' must be an object")
    for name, config in raw.items():
        label = f"MCP server '{name}'"
        if not isinstance(name, str) or not name.strip() or not isinstance(config, dict):
            raise ValueError(f"{source}: {label} must have a non-empty name and object config")
        transport = config.get("type")
        if "type" in config and transport not in ("stdio", "local", "http", "sse"):
            raise ValueError(f"{source}: {label} has unsupported transport type {transport!r}")
        has_command = "command" in config
        has_url = "url" in config
        if has_command == has_url:
            raise ValueError(f"{source}: {label} requires exactly one of 'command' or 'url'")
        if (
            transport in ("http", "sse")
            and not has_url
            or (transport in ("stdio", "local") and not has_command)
        ):
            raise ValueError(f"{source}: {label} transport does not match command/url")
        for key in ("command", "url", "cwd"):
            if key in config:
                _string_field(config, key, source, required=True)
        if has_url:
            try:
                url = urlsplit(config["url"])
                if url.scheme not in ("http", "https") or not url.hostname:
                    raise ValueError("expected an absolute HTTP(S) URL")
                _ = url.port
            except ValueError as exc:
                raise ValueError(f"{source}: {label} invalid 'url': {exc}") from exc
        for key in ("args", "tools"):
            if key in config and (
                not isinstance(config[key], list)
                or any(not isinstance(item, str) for item in config[key])
            ):
                raise ValueError(f"{source}: {label} '{key}' must be a list of strings")
        if "tools" in config and any(not tool.strip() for tool in config["tools"]):
            raise ValueError(f"{source}: {label} 'tools' entries must be non-empty strings")
        for key in ("env", "headers"):
            if key in config and (
                not isinstance(config[key], dict)
                or any(
                    not isinstance(k, str) or not isinstance(v, str) for k, v in config[key].items()
                )
            ):
                raise ValueError(f"{source}: {label} '{key}' must be a string-to-string object")
        if "timeout" in config and (
            isinstance(config["timeout"], bool)
            or not isinstance(config["timeout"], (int, float))
            or not math.isfinite(config["timeout"])
            or config["timeout"] <= 0
        ):
            raise ValueError(f"{source}: {label} 'timeout' must be a positive number")
    return dict(raw)


def _parse_hooks(plugin_dir: Path, manifest: dict[str, Any]) -> list[HookDefinition]:
    """Parse hooks from hooks.json or plugin.json hooks field."""
    hooks_file = plugin_dir / "hooks.json"
    source = plugin_dir / "plugin.json"
    raw = manifest.get("hooks", [])
    # Validate both declared sources; a valid file cannot hide invalid inline hooks.
    if not isinstance(raw, list):
        raise ValueError(f"{source}: 'hooks' must be a list")
    hooks = [_hook_from_dict(entry, source) for entry in raw]
    if hooks_file.exists():
        raw = _read_json(hooks_file)
        if not isinstance(raw, list):
            raise ValueError(f"{hooks_file}: hooks must be a list")
        return [_hook_from_dict(entry, hooks_file) for entry in raw]
    return hooks


def _hook_from_dict(data: Any, source: Path) -> HookDefinition:
    """Create a HookDefinition from a dict."""
    if not isinstance(data, dict):
        msg = f"{source}: Hook entry must be an object, got {type(data).__name__}"
        raise ValueError(msg)
    return HookDefinition(
        event=_string_field(data, "event", source, required=True),
        command=_string_field(data, "command", source, required=True),
        pattern=_string_field(data, "pattern", source, allow_empty=True),
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
    if isinstance(listed, str):
        listed = [listed]
    if not isinstance(listed, list) or any(
        not isinstance(entry, str) or not entry.strip() for entry in listed
    ):
        raise ValueError(
            f"{plugin_dir / 'plugin.json'}: 'instructions' must be a path or list of paths"
        )
    for entry in listed:
        _append_file_content(parts, plugin_dir / entry, required=True)

    return "\n\n".join(parts)


def _discover_extensions(plugin_dir: Path) -> list[Path]:
    """Discover extension.mjs files in extensions/ subdirectory."""
    ext_dir = plugin_dir / "extensions"
    if not ext_dir.is_dir():
        return []
    return sorted(ext_dir.glob("extension.mjs"))
