"""Configuration file loaders for Copilot and Claude Code projects.

Provides utilities for loading MCP server configurations from standard
config files (``.mcp.json``, ``.vscode/mcp.json``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


def load_mcp_config(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load MCP server configs from a ``.mcp.json`` file.

    Supports both Claude Code / root-level ``.mcp.json`` and VS Code
    ``.vscode/mcp.json`` formats.  Handles two common top-level keys:

    * ``mcpServers`` — Claude Code / standard MCP convention
    * ``servers`` — VS Code ``mcp.json`` convention

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

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in MCP config {path}: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(raw, dict):
        msg = f"MCP config must be a JSON object, got {type(raw).__name__}"
        raise ValueError(msg)

    # Try standard keys in priority order
    servers: dict[str, Any] | None = None
    for key in ("mcpServers", "servers"):
        if key in raw and isinstance(raw[key], dict):
            servers = raw[key]
            break

    if servers is None:
        _logger.warning("No 'mcpServers' or 'servers' key found in %s", path)
        return {}

    return dict(servers)
