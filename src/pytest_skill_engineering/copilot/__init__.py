"""GitHub Copilot coding agent support for pytest-skill-engineering.

Provides ``CopilotEval``, ``CopilotResult``, ``run_copilot``, and IDE
personas for testing real coding agents via the GitHub Copilot SDK.

Install with: ``uv add pytest-skill-engineering[copilot]``
"""

from __future__ import annotations

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.evals import load_custom_agent, load_custom_agents
from pytest_skill_engineering.copilot.fixtures import copilot_eval
from pytest_skill_engineering.copilot.model import CopilotModel
from pytest_skill_engineering.copilot.personas import (
    ClaudeCodePersona,
    CopilotCLIPersona,
    HeadlessPersona,
    Persona,
    VSCodePersona,
)
from pytest_skill_engineering.copilot.result import CopilotResult
from pytest_skill_engineering.copilot.runner import run_copilot
from pytest_skill_engineering.execution.optimizer import InstructionSuggestion, optimize_instruction

__all__ = [
    "CopilotEval",
    "CopilotModel",
    "CopilotResult",
    "InstructionSuggestion",
    "ClaudeCodePersona",
    "CopilotCLIPersona",
    "HeadlessPersona",
    "Persona",
    "VSCodePersona",
    "copilot_eval",
    "load_custom_agent",
    "load_custom_agents",
    "optimize_instruction",
    "run_copilot",
]
