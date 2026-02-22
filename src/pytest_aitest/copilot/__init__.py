"""GitHub Copilot coding agent support for pytest-aitest.

Provides ``CopilotAgent``, ``CopilotResult``, ``run_copilot``, and IDE
personas for testing real coding agents via the GitHub Copilot SDK.

Install with: ``uv add pytest-aitest[copilot]``
"""

from __future__ import annotations

from pytest_aitest.copilot.agent import CopilotAgent
from pytest_aitest.copilot.agents import load_custom_agent, load_custom_agents
from pytest_aitest.copilot.fixtures import copilot_run
from pytest_aitest.copilot.model import CopilotModel
from pytest_aitest.copilot.personas import (
    ClaudeCodePersona,
    CopilotCLIPersona,
    HeadlessPersona,
    Persona,
    VSCodePersona,
)
from pytest_aitest.copilot.result import CopilotResult
from pytest_aitest.copilot.runner import run_copilot
from pytest_aitest.execution.optimizer import InstructionSuggestion, optimize_instruction

__all__ = [
    "CopilotAgent",
    "CopilotModel",
    "CopilotResult",
    "InstructionSuggestion",
    "ClaudeCodePersona",
    "CopilotCLIPersona",
    "HeadlessPersona",
    "Persona",
    "VSCodePersona",
    "copilot_run",
    "load_custom_agent",
    "load_custom_agents",
    "optimize_instruction",
    "run_copilot",
]
