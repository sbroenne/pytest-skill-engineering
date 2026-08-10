"""Shared Copilot runtime contracts and SDK-backed type aliases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeAlias

from copilot.session import CustomAgentConfig, MCPServerConfig, ReasoningEffort, SessionHooks

CopilotCustomAgentConfig: TypeAlias = CustomAgentConfig
CopilotMCPServerConfig: TypeAlias = MCPServerConfig
CopilotReasoningEffort: TypeAlias = ReasoningEffort
CopilotSessionHooks: TypeAlias = SessionHooks
SubagentStatus: TypeAlias = Literal["selected", "started", "completed", "failed"]


class CopilotResultAgent(Protocol):
    """Minimal agent surface stored on :class:`CopilotResult`."""

    @property
    def working_directory(self) -> str | None:
        raise NotImplementedError


@dataclass(slots=True)
class SubagentInvocation:
    """A single custom-agent dispatch observed during a run."""

    invocation_id: str
    name: str
    status: SubagentStatus
    duration_ms: float | None = None


def declared_agent_tools(
    agent_config: CopilotCustomAgentConfig,
) -> list[str] | None:
    """Return the exact tool allowlist declared on a custom agent."""
    if "tools" not in agent_config:
        return None
    return agent_config["tools"]


def merge_agent_mcp_servers(
    parent_servers: Mapping[str, CopilotMCPServerConfig],
    agent_config: CopilotCustomAgentConfig,
) -> dict[str, CopilotMCPServerConfig]:
    """Merge parent MCP servers with any exact custom-agent overrides."""
    merged = dict(parent_servers)
    agent_servers = agent_config.get("mcp_servers")
    if agent_servers:
        merged.update(agent_servers)
    return merged


def resolve_agent_reasoning_effort(
    *,
    parent_model: str | None,
    parent_reasoning_effort: CopilotReasoningEffort | None,
    agent_config: CopilotCustomAgentConfig,
) -> CopilotReasoningEffort | None:
    """Resolve a custom agent's reasoning effort like the current SDK contract."""
    if "reasoning_effort" in agent_config:
        return agent_config["reasoning_effort"]

    agent_model = agent_config.get("model")
    if agent_model is None or agent_model == parent_model:
        return parent_reasoning_effort

    return None


def require_custom_agent_prompt(
    agent_config: CopilotCustomAgentConfig,
) -> str:
    """Return the declared prompt or raise when the runtime contract is broken."""
    prompt = agent_config.get("prompt")
    if isinstance(prompt, str) and prompt:
        return prompt
    msg = f"Custom agent '{agent_config.get('name', 'unknown')}' is missing a prompt"
    raise ValueError(msg)


def require_custom_agent_name(
    agent_config: CopilotCustomAgentConfig,
) -> str:
    """Return the declared machine name or raise when the runtime contract is broken."""
    name = agent_config.get("name")
    if isinstance(name, str) and name:
        return name
    raise ValueError("Custom agent is missing a name")


def require_mapping(arguments: Any) -> dict[str, Any]:
    """Validate tool arguments that must be object-shaped."""
    if isinstance(arguments, dict):
        return arguments
    msg = "Custom-agent dispatch arguments must be an object"
    raise ValueError(msg)
