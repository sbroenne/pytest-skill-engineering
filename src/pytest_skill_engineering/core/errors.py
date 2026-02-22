"""Custom exceptions for pytest-skill-engineering."""

from __future__ import annotations


class AITestError(Exception):
    """Base exception for pytest-skill-engineering errors."""


class ServerStartError(AITestError):
    """Error starting an MCP or CLI server."""

    def __init__(self, server_type: str, command: list[str], message: str) -> None:
        self.server_type = server_type
        self.command = command
        super().__init__(f"Failed to start {server_type} server ({' '.join(command)}): {message}")


class EngineTimeoutError(AITestError):
    """Eval engine timed out."""

    def __init__(self, timeout_ms: int, turns_completed: int) -> None:
        self.timeout_ms = timeout_ms
        self.turns_completed = turns_completed
        super().__init__(f"Eval timed out after {timeout_ms}ms ({turns_completed} turns completed)")


class ToolCallError(AITestError):
    """Error calling a tool."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class RateLimitError(AITestError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f" (retry after {retry_after}s)"
        super().__init__(msg)
