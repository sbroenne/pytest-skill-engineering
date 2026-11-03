"""Shared validation for plugin, custom-agent, and MCP configuration fields."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


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
