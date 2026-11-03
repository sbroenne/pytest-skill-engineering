"""GitHub Copilot coding agent support for pytest-copilot.

Provides ``CopilotTask``, ``CopilotResult``, ``run_copilot``, and IDE
personas for testing real coding agents via the GitHub Copilot SDK.

Install with: ``uv add pytest-copilot``
"""

from __future__ import annotations

from pytest_copilot.copilot.api import run_copilot
from pytest_copilot.copilot.commands import CommandCancelledError, create_command_tool
from pytest_copilot.copilot.config import load_mcp_config
from pytest_copilot.copilot.fixtures import copilot_run
from pytest_copilot.copilot.personas import (
    ClaudeCodePersona,
    CopilotCLIPersona,
    HeadlessPersona,
    Persona,
    VSCodePersona,
)
from pytest_copilot.copilot.requests import RequestAudit
from pytest_copilot.copilot.result import CopilotResult, UsageInfo
from pytest_copilot.copilot.task import CopilotTask
from pytest_copilot.core.evals import load_custom_agent, load_custom_agents
from pytest_copilot.core.result import DiscoveredSkill, SkillDiscovery

__all__ = [
    "CommandCancelledError",
    "create_command_tool",
    "CopilotTask",
    "CopilotResult",
    "DiscoveredSkill",
    "RequestAudit",
    "SkillDiscovery",
    "UsageInfo",
    "ClaudeCodePersona",
    "CopilotCLIPersona",
    "HeadlessPersona",
    "Persona",
    "VSCodePersona",
    "copilot_run",
    "load_custom_agent",
    "load_custom_agents",
    "load_mcp_config",
    "run_copilot",
]
