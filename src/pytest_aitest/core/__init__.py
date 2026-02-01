"""Core module - agent configuration and result types."""

from pytest_aitest.core.agent import (
    Agent,
    CLIExecution,
    CLIServer,
    MCPServer,
    Provider,
    Wait,
)
from pytest_aitest.core.errors import AITestError, EngineTimeoutError, ServerStartError
from pytest_aitest.core.prompt import Prompt, load_prompt, load_prompts
from pytest_aitest.core.result import AgentResult, ToolCall, Turn
from pytest_aitest.core.skill import Skill, SkillError, SkillMetadata, load_skill

__all__ = [
    "Agent",
    "AgentResult",
    "AITestError",
    "CLIExecution",
    "CLIServer",
    "EngineTimeoutError",
    "MCPServer",
    "Prompt",
    "Provider",
    "ServerStartError",
    "Skill",
    "SkillError",
    "SkillMetadata",
    "ToolCall",
    "Turn",
    "Wait",
    "load_prompt",
    "load_prompts",
    "load_skill",
]
