"""Result models for agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolCall:
    """A tool call made by the agent."""

    name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None

    def __repr__(self) -> str:
        status = "error" if self.error else "ok"
        return f"ToolCall({self.name}, {status})"


@dataclass(slots=True)
class Turn:
    """A single conversational turn."""

    role: str  # "user", "assistant", "tool"
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Get the text content of this turn."""
        return self.content

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Turn({self.role}: {preview!r})"


@dataclass(slots=True)
class AgentResult:
    """Result of running an agent with rich inspection capabilities.

    Example:
        result = await aitest_run(agent, "Hello!")
        assert result.success
        assert "hello" in result.final_response.lower()
        assert result.tool_was_called("read_file")
    """

    turns: list[Turn]
    success: bool
    error: str | None = None
    duration_ms: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0

    @property
    def final_response(self) -> str:
        """Get the last assistant response."""
        for turn in reversed(self.turns):
            if turn.role == "assistant":
                return turn.content
        return ""

    @property
    def all_responses(self) -> list[str]:
        """Get all assistant responses."""
        return [t.content for t in self.turns if t.role == "assistant"]

    @property
    def all_tool_calls(self) -> list[ToolCall]:
        """Get all tool calls across all turns."""
        calls = []
        for turn in self.turns:
            calls.extend(turn.tool_calls)
        return calls

    @property
    def tool_names_called(self) -> set[str]:
        """Get set of all tool names that were called."""
        return {call.name for call in self.all_tool_calls}

    def tool_was_called(self, name: str) -> bool:
        """Check if a specific tool was called."""
        return name in self.tool_names_called

    def tool_call_count(self, name: str) -> int:
        """Count how many times a specific tool was called."""
        return len(self.tool_calls_for(name))

    def tool_calls_for(self, name: str) -> list[ToolCall]:
        """Get all calls to a specific tool."""
        return [c for c in self.all_tool_calls if c.name == name]

    def tool_call_arg(self, tool_name: str, arg_name: str) -> Any:
        """Get argument value from the first call to a tool.

        Args:
            tool_name: Name of the tool
            arg_name: Name of the argument

        Returns:
            Argument value or None if not found
        """
        calls = self.tool_calls_for(tool_name)
        if calls:
            return calls[0].arguments.get(arg_name)
        return None

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED: {self.error}"
        tools = ", ".join(sorted(self.tool_names_called)) or "none"
        cost_str = f"${self.cost_usd:.6f}" if self.cost_usd > 0 else "N/A"
        tokens = self.token_usage.get("prompt", 0) + self.token_usage.get("completion", 0)
        return (
            f"AgentResult({status})\n"
            f"  Turns: {len(self.turns)}\n"
            f"  Tools called: {tools}\n"
            f"  Duration: {self.duration_ms:.0f}ms\n"
            f"  Tokens: {tokens} | Cost: {cost_str}\n"
            f"  Final: {self.final_response[:100]!r}..."
        )

    def __bool__(self) -> bool:
        return self.success
