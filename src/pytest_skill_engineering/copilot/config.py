"""Configuration file loaders for Copilot and Claude Code projects.

Provides utilities for loading MCP server configurations from standard
config files (``.mcp.json``, ``.vscode/mcp.json``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_skill_engineering.core.plugin import _read_json, _validate_mcp_servers


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
