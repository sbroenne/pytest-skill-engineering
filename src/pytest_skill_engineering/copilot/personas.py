"""IDE Personas for pytest-skill-engineering Copilot support.

A ``Persona`` defines the runtime environment in which an agent under test
is expected to run.  Each persona ensures the agent has the correct tool set
for its target IDE by injecting polyfill tools and adding a system-message
fragment that sets context.

Built-in personas
-----------------
``VSCodePersona`` (default)
    Simulates the VS Code Copilot extension.  Polyfills ``runSubagent`` so
    that agents written for VS Code dispatch sub-agents correctly.

``ClaudeCodePersona``
    Simulates Claude Code.  Polyfills a ``task``-dispatch tool (same
    mechanism as ``runSubagent``, named ``task`` to match Claude Code's
    native API).

``CopilotCLIPersona``
    Simulates the GitHub Copilot terminal agent.  No polyfills are needed —
    ``task`` and ``skill`` are already in the SDK's native 16-tool set.
    Adds a system-message fragment so the model knows its environment.

``HeadlessPersona``
    Raw SDK headless mode — no polyfills, no extra system message.  Use
    when you want to test exactly what the SDK exposes with no IDE context.

Usage::

    from pytest_skill_engineering.copilot import CopilotAgent, VSCodePersona, ClaudeCodePersona

    # Explicit — recommended for clarity
    agent = CopilotAgent(persona=VSCodePersona(), custom_agents=[...])

    # Default — VSCodePersona is used automatically
    agent = CopilotAgent(custom_agents=[...])

    # Headless — no IDE context, no polyfills
    agent = CopilotAgent(persona=HeadlessPersona())
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from copilot.types import Tool, ToolInvocation, ToolResult

    from pytest_skill_engineering.copilot.agent import CopilotAgent
    from pytest_skill_engineering.copilot.events import EventMapper


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Persona:
    """Base class for IDE runtime personas.

    Override ``apply()`` to inject polyfill tools and system-message
    additions that match your target IDE's native tool set.

    The ``apply()`` method is called by the runner *after*
    ``agent.build_session_config()`` and *before* the session is created,
    so modifications to ``session_config`` take effect immediately.

    Phase-2 extension point: override ``create_client()`` to swap the
    underlying SDK backend (e.g. Anthropic SDK for Claude Code).
    """

    def apply(
        self,
        agent: "CopilotAgent",
        session_config: dict[str, Any],
        mapper: "EventMapper",
    ) -> None:
        """Modify *session_config* in-place to match this persona's environment.

        Args:
            agent: The ``CopilotAgent`` being executed (read-only).
            session_config: The session config dict built from ``agent``.
                Mutate this to inject tools, update system_message, etc.
            mapper: The ``EventMapper`` for the current run.  Pass to
                tool handlers that need to record subagent events.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ---------------------------------------------------------------------------
# Headless (raw SDK baseline)
# ---------------------------------------------------------------------------


class HeadlessPersona(Persona):
    """Raw SDK headless mode — no polyfills, no IDE system message.

    Use this when you want to test exactly what the Copilot SDK exposes
    with no runtime context added.  This is the minimal baseline.
    """


# ---------------------------------------------------------------------------
# GitHub Copilot CLI
# ---------------------------------------------------------------------------


class CopilotCLIPersona(Persona):
    """GitHub Copilot terminal agent persona.

    ``task`` and ``skill`` are already in the SDK's native 16-tool set, so
    no polyfills are needed.  This persona only adds a system-message
    fragment so the model knows it is running inside the Copilot CLI and
    can use ``task`` for sub-task dispatch.
    """

    _SYSTEM_MSG = "You are running inside GitHub Copilot CLI."
    _INSTRUCTIONS_FILE = Path(".github") / "copilot-instructions.md"

    def apply(
        self,
        agent: "CopilotAgent",
        session_config: dict[str, Any],
        mapper: "EventMapper",
    ) -> None:
        _prepend_system_message(session_config, self._SYSTEM_MSG)
        if agent.working_directory:
            custom = _load_custom_instructions_file(
                Path(agent.working_directory) / self._INSTRUCTIONS_FILE
            )
            if custom:
                _prepend_system_message(session_config, custom)


# ---------------------------------------------------------------------------
# VS Code
# ---------------------------------------------------------------------------


class VSCodePersona(Persona):
    """VS Code Copilot extension persona.

    Polyfills ``runSubagent`` so agents written for VS Code (where
    ``runSubagent`` is a native tool) can dispatch custom sub-agents
    correctly during testing.

    The polyfill is only injected when ``agent.custom_agents`` is non-empty,
    so using this persona with a plain agent has no side-effects.
    """

    _SYSTEM_MSG = "You are running inside VS Code."
    _INSTRUCTIONS_FILE = Path(".github") / "copilot-instructions.md"

    def apply(
        self,
        agent: "CopilotAgent",
        session_config: dict[str, Any],
        mapper: "EventMapper",
    ) -> None:
        _prepend_system_message(session_config, self._SYSTEM_MSG)
        if agent.working_directory:
            custom = _load_custom_instructions_file(
                Path(agent.working_directory) / self._INSTRUCTIONS_FILE
            )
            if custom:
                _prepend_system_message(session_config, custom)
        if agent.custom_agents:
            tool = _make_runsubagent_tool(agent, agent.custom_agents, mapper)
            _inject_tool(session_config, tool)
            agents_block = _build_agents_block(agent.custom_agents, tool_name="runSubagent")
            _prepend_system_message(session_config, agents_block)


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------


class ClaudeCodePersona(Persona):
    """Claude Code persona.

    Polyfills a ``task``-dispatch tool (same dispatch mechanism as
    ``runSubagent``, named ``task`` to match Claude Code's native API) so
    agents written for Claude Code can dispatch sub-agents during testing.

    The polyfill is only injected when ``agent.custom_agents`` is non-empty.
    """

    _SYSTEM_MSG = "You are running inside Claude Code."
    _INSTRUCTIONS_FILE = Path("CLAUDE.md")

    def apply(
        self,
        agent: "CopilotAgent",
        session_config: dict[str, Any],
        mapper: "EventMapper",
    ) -> None:
        _prepend_system_message(session_config, self._SYSTEM_MSG)
        if agent.working_directory:
            custom = _load_custom_instructions_file(
                Path(agent.working_directory) / self._INSTRUCTIONS_FILE
            )
            if custom:
                _prepend_system_message(session_config, custom)
        if agent.custom_agents:
            tool = _make_task_tool(agent, agent.custom_agents, mapper)
            _inject_tool(session_config, tool)
            agents_block = _build_agents_block(agent.custom_agents, tool_name="task")
            _prepend_system_message(session_config, agents_block)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_custom_instructions_file(file_path: Path) -> str | None:
    """Read a custom instructions file and return its content, or None if absent."""
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8").strip()
        return content or None
    return None


def _prepend_system_message(session_config: dict[str, Any], message: str) -> None:
    """Prepend *message* to the system_message in *session_config*.

    If no system_message is set, creates one in "append" mode so it is
    added to the CLI's built-in system message rather than replacing it.
    """
    existing = session_config.get("system_message") or {}
    existing_content: str = existing.get("content") or ""
    mode: str = existing.get("mode") or "append"
    combined = f"{message}\n\n{existing_content}".strip()
    session_config["system_message"] = {"mode": mode, "content": combined}


def _inject_tool(session_config: dict[str, Any], tool: "Tool") -> None:
    """Append *tool* to the tools list in *session_config*."""
    existing: list[Any] = list(session_config.get("tools") or [])
    session_config["tools"] = existing + [tool]


def _build_agents_block(custom_agents: list[dict[str, Any]], tool_name: str = "runSubagent") -> str:
    """Build the <agents> XML block that VS Code injects into the system prompt.

    Mirrors ``computeAutomaticInstructions.ts`` in ``microsoft/vscode``:
    lists available subagents by name and description so the model knows
    which agents to dispatch and how to call them.

    Args:
        custom_agents: List of custom agent config dicts (each with at least
            a ``name`` key, optionally ``description`` and ``argument_hint``).
        tool_name: Name of the dispatch tool (``runSubagent`` for VS Code,
            ``task`` for Claude Code).

    Returns:
        The ``<agents>…</agents>`` XML string to prepend to the system message.
    """
    lines: list[str] = [
        "<agents>",
        "Here is a list of agents that can be used when running a subagent.",
        (
            "Each agent has optionally a description with the agent's purpose "
            "and expertise. When asked to run a subagent, choose the most "
            "appropriate agent from this list."
        ),
        f"Use the {tool_name} tool with the agent name to run the subagent.",
        (
            f"You are an orchestrator. All task work must be delegated to "
            f"subagents via the `{tool_name}` tool. "
            f"Do not implement, edit files, or perform task work directly — "
            f"delegate every phase of work to the appropriate subagent."
        ),
    ]
    for a in custom_agents:
        lines.append("<agent>")
        lines.append(f"<name>{a['name']}</name>")
        if desc := a.get("description"):
            lines.append(f"<description>{desc}</description>")
        if hint := a.get("argument_hint") or a.get("argumentHint"):
            lines.append(f"<argumentHint>{hint}</argumentHint>")
        lines.append("</agent>")
    lines.append("</agents>")
    return "\n".join(lines)


def _make_runsubagent_tool(
    parent_agent: "CopilotAgent",
    custom_agents: list[dict[str, Any]],
    mapper: "EventMapper",
) -> "Tool":
    """Build a ``runSubagent`` polyfill tool for the VS Code persona."""
    return _make_subagent_dispatch_tool("runSubagent", parent_agent, custom_agents, mapper)


def _make_task_tool(
    parent_agent: "CopilotAgent",
    custom_agents: list[dict[str, Any]],
    mapper: "EventMapper",
) -> "Tool":
    """Build a ``task`` polyfill tool for the Claude Code persona."""
    return _make_subagent_dispatch_tool("task", parent_agent, custom_agents, mapper)


def _make_subagent_dispatch_tool(
    tool_name: str,
    parent_agent: "CopilotAgent",
    custom_agents: list[dict[str, Any]],
    mapper: "EventMapper",
) -> "Tool":
    """Build a subagent dispatch polyfill tool.

    The Copilot CLI does not natively expose ``runSubagent`` or ``task`` in
    SDK headless mode.  This factory creates a Python-side ``Tool`` that
    dispatches registered custom agents as nested ``run_copilot`` calls.

    Args:
        tool_name: Name to register the tool as (``"runSubagent"`` for VS Code,
            ``"task"`` for Claude Code).
        parent_agent: The orchestrator ``CopilotAgent`` being executed.
        custom_agents: List of custom agent config dicts (each with at least
            a ``name`` key, optionally ``prompt``, ``description``).
        mapper: The ``EventMapper`` for the current run, used to record
            subagent lifecycle events.
    """
    from copilot.types import Tool, ToolResult

    from pytest_skill_engineering.copilot.agent import CopilotAgent as _CopilotAgent
    from pytest_skill_engineering.copilot.runner import run_copilot

    agent_map: dict[str, dict[str, Any]] = {a["name"]: a for a in custom_agents}

    async def _handler(invocation: "ToolInvocation") -> "ToolResult":
        args: dict[str, Any] = invocation.get("arguments") or {}  # type: ignore[assignment]

        agent_name: str | None = (
            args.get("agent_name") or args.get("agent") or args.get("agentName")
        )
        prompt_text: str = (
            args.get("prompt")
            or args.get("message")
            or args.get("task")
            or args.get("description")
            or ""
        )

        if not agent_name:
            available = sorted(agent_map)
            return ToolResult(
                textResultForLlm=(f"Error: agent_name is required. Available agents: {available}"),
                resultType="failure",
            )

        agent_cfg = agent_map.get(agent_name)
        if agent_cfg is None:
            available = sorted(agent_map)
            return ToolResult(
                textResultForLlm=(f"Error: agent '{agent_name}' not found. Available: {available}"),
                resultType="failure",
            )

        mapper.record_subagent_start(agent_name)

        sub_agent = _CopilotAgent(
            name=agent_name,
            model=parent_agent.model,
            instructions=agent_cfg.get("prompt"),
            working_directory=parent_agent.working_directory,
            timeout_s=min(parent_agent.timeout_s, 600.0),
            max_turns=min(parent_agent.max_turns, 30),
            auto_confirm=True,
        )

        sub_result = await run_copilot(sub_agent, prompt_text)

        if sub_result.success:
            mapper.record_subagent_complete(agent_name)
            return ToolResult(
                textResultForLlm=sub_result.final_response or "Sub-agent completed.",
                resultType="success",
            )

        mapper.record_subagent_failed(agent_name)
        return ToolResult(
            textResultForLlm=f"Sub-agent '{agent_name}' failed: {sub_result.error}",
            resultType="failure",
        )

    return Tool(
        name=tool_name,
        description=(
            f"Dispatch a named agent to perform a task using the {tool_name} tool. "
            "The agent runs with its own instructions and returns its final response. "
            f"Available agents: {sorted(agent_map)}"
        ),
        handler=_handler,
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent to dispatch.",
                    "enum": sorted(agent_map),
                },
                "prompt": {
                    "type": "string",
                    "description": "Task or message to send to the agent.",
                },
            },
            "required": ["agent_name", "prompt"],
        },
    )
