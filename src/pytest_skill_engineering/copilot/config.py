"""Configuration file loaders for Copilot and Claude Code projects.

Provides utilities for loading MCP server configurations from standard
config files (``.mcp.json``, ``.vscode/mcp.json``).
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_skill_engineering.core.plugin import _read_json
from pytest_skill_engineering.core.validation import _validate_mcp_servers

if TYPE_CHECKING:
    from pytest_skill_engineering.copilot.contracts import CopilotEvalConfig


def snapshot_session_configuration(
    agent: CopilotEvalConfig, session_config: dict[str, Any]
) -> dict[str, Any]:
    """Capture prepared settings without handlers, credentials, or server environments."""
    system = session_config.get("system_message") or {}
    snapshot = {
        "name": agent.name,
        "model": session_config.get("model"),
        "instructions": system.get("content"),
        "system_message_mode": system.get("mode"),
        "reasoning_effort": session_config.get("reasoning_effort"),
        "client_mode": agent.client_mode,
        "image_detail": agent.image_detail,
        "audit_requests": agent.audit_requests,
        "max_tool_calls": agent.max_tool_calls,
        "max_turns": agent.max_turns,
        "timeout_s": agent.timeout_s,
        "auto_confirm": agent.auto_confirm,
        "allowed_tools": session_config.get("available_tools"),
        "excluded_tools": session_config.get("excluded_tools"),
        "skill_directories": session_config.get("skill_directories", []),
        "disabled_skills": session_config.get("disabled_skills", []),
        "active_agent": session_config.get("agent"),
        "working_directory": session_config.get("working_directory"),
        "persona": type(agent.persona).__name__,
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "metadata": tool.metadata,
            }
            for tool in session_config.get("tools") or []
        ],
        "mcp_servers": {
            name: {"type": config.get("type"), "tools": config.get("tools")}
            for name, config in (session_config.get("mcp_servers") or {}).items()
        },
        "custom_agents": [
            {
                key: value
                for key, value in custom.items()
                if key
                in {
                    "name",
                    "prompt",
                    "description",
                    "display_name",
                    "model",
                    "reasoning_effort",
                    "tools",
                    "infer",
                    "skills",
                }
            }
            for custom in session_config.get("custom_agents") or []
        ],
    }
    for key in (
        "enable_config_discovery",
        "enable_file_hooks",
        "enable_on_demand_instruction_discovery",
        "skip_custom_instructions",
        "enable_managed_settings",
        "enable_skills",
    ):
        if key in session_config:
            snapshot[key] = session_config[key]
    return deepcopy(snapshot)


def load_mcp_config(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load MCP server configs from a ``.mcp.json`` file.

    Supports both Claude Code / root-level ``.mcp.json`` and VS Code
    ``.vscode/mcp.json`` formats.  Handles two common top-level keys:

    * ``mcpServers`` — Claude Code / standard MCP convention
    * ``servers`` — VS Code ``mcp.json`` convention

    Exactly one supported key must be present. An explicit empty mapping is valid;
    missing keys, conflicting keys, and malformed server definitions raise errors.

    Returns:
        Dict of ``server_name → config`` compatible with
        ``CopilotEval(mcp_servers=...)``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not valid JSON or has unexpected structure.

    Example::

        from pytest_skill_engineering.copilot.config import load_mcp_config

        servers = load_mcp_config(".mcp.json")
        agent = CopilotEval(mcp_servers=servers)
    """
    path = Path(path)
    if not path.is_file():
        msg = f"MCP config file not found: {path}"
        raise FileNotFoundError(msg)

    raw = _read_json(path)

    if not isinstance(raw, dict):
        msg = f"{path}: MCP config must be a JSON object, got {type(raw).__name__}"
        raise ValueError(msg)

    fields = [key for key in ("mcpServers", "servers") if key in raw]
    if len(fields) != 1:
        raise ValueError(f"{path}: specify exactly one of 'mcpServers' and 'servers'")

    return _validate_mcp_servers(raw[fields[0]], path, field=fields[0])
