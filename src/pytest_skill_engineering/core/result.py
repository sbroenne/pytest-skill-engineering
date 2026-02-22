"""Result models for agent execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ImageContent:
    """Binary image data returned by a tool call.

    Example:
        screenshots = result.tool_images_for("screenshot")
        assert len(screenshots) > 0
        assert screenshots[-1].media_type == "image/png"
    """

    data: bytes
    media_type: str  # e.g. "image/png"

    def __repr__(self) -> str:
        return f"ImageContent({self.media_type}, {len(self.data)} bytes)"


@dataclass(slots=True)
class ToolCall:
    """A tool call made by the agent."""

    name: str
    arguments: dict[str, Any]
    result: str | None = None
    error: str | None = None
    duration_ms: float | None = None
    image_content: bytes | None = None
    image_media_type: str | None = None

    def __repr__(self) -> str:
        status = "error" if self.error else "ok"
        timing = f", {self.duration_ms:.1f}ms" if self.duration_ms else ""
        image = ", image" if self.image_content else ""
        return f"ToolCall({self.name}, {status}{timing}{image})"


@dataclass(slots=True)
class ToolInfo:
    """Metadata about an MCP tool for AI analysis.

    Captures the tool's description and schema as exposed to the LLM,
    enabling the AI to analyze whether tool descriptions are clear and
    suggest improvements.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

    def __repr__(self) -> str:
        return f"ToolInfo({self.name} from {self.server_name})"


@dataclass(slots=True)
class MCPPromptArgument:
    """An argument for an MCP prompt template."""

    name: str
    description: str = ""
    required: bool = False

    def __repr__(self) -> str:
        req = ", required" if self.required else ""
        return f"MCPPromptArgument({self.name!r}{req})"


@dataclass(slots=True)
class MCPPrompt:
    """A prompt template exposed by an MCP server.

    MCP servers can bundle reusable prompt templates alongside their tools.
    These appear in VS Code as slash commands (e.g. ``/mcp.servername.promptname``).
    Use :meth:`MCPServerProcess.list_prompts` to discover them and
    :meth:`MCPServerProcess.get_prompt` to render one with arguments.

    Example:
        server = MCPServerProcess(mcp_config)
        await server.start()
        prompts = await server.list_prompts()
        messages = await server.get_prompt("code_review", {"code": "..."})
        result = await eval_run(agent, messages[0]["content"])
    """

    name: str
    description: str = ""
    arguments: list[MCPPromptArgument] = field(default_factory=list)

    def __repr__(self) -> str:
        args = f", {len(self.arguments)} args" if self.arguments else ""
        return f"MCPPrompt({self.name!r}{args})"


@dataclass(slots=True)
class SkillInfo:
    """Metadata about a skill for AI analysis.

    Captures the skill's instruction content and references,
    enabling the AI to analyze skill effectiveness and suggest improvements.
    """

    name: str
    description: str
    instruction_content: str
    reference_names: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        refs = f", {len(self.reference_names)} refs" if self.reference_names else ""
        return f"SkillInfo({self.name}{refs})"


@dataclass(slots=True)
class ClarificationStats:
    """Statistics about clarification requests detected during execution.

    Tracks when the agent asks for user input instead of executing the task.
    Only populated when clarification_detection is enabled on the agent.

    Example:
        result = await eval_run(agent, "Check my balance")
        if result.clarification_stats:
            print(f"Eval asked {result.clarification_stats.count} question(s)")
    """

    count: int = 0
    turn_indices: list[int] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)  # Max 3 examples stored

    def __repr__(self) -> str:
        return f"ClarificationStats(count={self.count}, turns={self.turn_indices})"


@dataclass(slots=True)
class Assertion:
    """A single assertion result from a test."""

    type: str  # "semantic", "condition", etc.
    passed: bool
    message: str
    details: str | None = None

    def __repr__(self) -> str:
        status = "✓" if self.passed else "✗"
        return f"Assertion({status} {self.message})"


@dataclass(slots=True)
class SubagentInvocation:
    """A subagent invocation observed during agent execution.

    Tracks when an orchestrator agent dispatches work to a named sub-agent,
    along with the final status and duration of that invocation.

    Example:
        result = await copilot_eval(agent, "Build and test the project")
        assert any(s.name == "coder" for s in result.subagent_invocations)
        assert all(s.status == "completed" for s in result.subagent_invocations)
    """

    name: str
    status: str  # "selected", "started", "completed", "failed"
    duration_ms: float | None = None

    def __repr__(self) -> str:
        return f"SubagentInvocation({self.name}, {self.status})"


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
class EvalResult:
    """Result of running an agent with rich inspection capabilities.

    Example:
        result = await eval_run(agent, "Hello!")
        assert result.success
        assert "hello" in result.final_response.lower()
        assert result.tool_was_called("read_file")

        # Session continuity: pass messages to next test
        next_result = await eval_run(agent, "Follow up", messages=result.messages)
    """

    turns: list[Turn]
    success: bool
    error: str | None = None
    duration_ms: float = 0.0
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    _messages: list[Any] = field(default_factory=list)
    session_context_count: int = 0  # Number of prior messages passed in
    assertions: list[Assertion] = field(default_factory=list)  # Assertion results

    # Phase 2: Collection for AI analysis
    available_tools: list[ToolInfo] = field(default_factory=list)
    skill_info: SkillInfo | None = None
    effective_system_prompt: str = ""

    # Clarification detection
    clarification_stats: ClarificationStats | None = None

    @property
    def messages(self) -> list[Any]:
        """Get full conversation messages for session continuity.

        Use this to pass conversation history to the next test in a session:

            result = await eval_run(agent, "First message")
            next_result = await eval_run(agent, "Continue", messages=result.messages)
        """
        return list(self._messages)  # Return copy to prevent mutation

    @property
    def is_session_continuation(self) -> bool:
        """Check if this result is part of a multi-turn session.

        Returns True if prior messages were passed via the messages parameter.
        """
        return self.session_context_count > 0

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

    def tool_images_for(self, name: str) -> list[ImageContent]:
        """Get all images returned by a specific tool.

        Args:
            name: Name of the tool (e.g., "screenshot")

        Returns:
            List of ImageContent objects from tool calls that returned images.

        Example:
            screenshots = result.tool_images_for("screenshot")
            assert len(screenshots) > 0
            assert screenshots[-1].media_type == "image/png"
        """
        return [
            ImageContent(data=c.image_content, media_type=c.image_media_type or "image/png")
            for c in self.tool_calls_for(name)
            if c.image_content is not None
        ]

    @property
    def asked_for_clarification(self) -> bool:
        """Check if the agent asked for clarification instead of acting.

        Returns True if clarification detection was enabled AND the agent
        asked at least one clarifying question.

        Example:
            result = await eval_run(agent, "Check my balance")
            assert not result.asked_for_clarification
        """
        return self.clarification_stats is not None and self.clarification_stats.count > 0

    @property
    def clarification_count(self) -> int:
        """Number of times the agent asked for clarification."""
        if self.clarification_stats is None:
            return 0
        return self.clarification_stats.count

    @property
    def tool_context(self) -> str:
        """Summarise tool calls and their results as plain text.

        Use this as the ``context`` argument for ``llm_score`` so the judge
        can see what tools were called and what data they returned.

        Example::

            score = llm_score(
                result.final_response,
                TOOL_QUALITY_RUBRIC,
                context=result.tool_context,
            )
        """
        calls = self.all_tool_calls
        if not calls:
            return "No tools were called."
        lines: list[str] = []
        for i, call in enumerate(calls, 1):
            lines.append(f"## Tool call {i}: {call.name}")
            if call.arguments:
                args = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
                lines.append(f"Arguments: {args}")
            if call.error:
                lines.append(f"Error: {call.error}")
            elif call.result:
                lines.append(f"Result: {call.result}")
            lines.append("")
        return "\n".join(lines)

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED: {self.error}"
        tools = ", ".join(sorted(self.tool_names_called)) or "none"
        cost_str = f"${self.cost_usd:.6f}" if self.cost_usd > 0 else "N/A"
        tokens = self.token_usage.get("prompt", 0) + self.token_usage.get("completion", 0)
        return (
            f"EvalResult({status})\n"
            f"  Turns: {len(self.turns)}\n"
            f"  Tools called: {tools}\n"
            f"  Duration: {self.duration_ms:.0f}ms\n"
            f"  Tokens: {tokens} | Cost: {cost_str}\n"
            f"  Final: {self.final_response[:100]!r}..."
        )

    def __bool__(self) -> bool:
        return self.success
