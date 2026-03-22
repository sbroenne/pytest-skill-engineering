"""GitHub Copilot coding agent support for pytest-skill-engineering.

Provides ``CopilotEval``, ``CopilotResult``, ``run_copilot``, and IDE
personas for testing real coding agents via the GitHub Copilot SDK.

Install with: ``uv add pytest-skill-engineering[copilot]``
"""

from __future__ import annotations

from pytest_skill_engineering.copilot.config import load_mcp_config
from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.evals import load_custom_agent, load_custom_agents
from pytest_skill_engineering.copilot.fixtures import copilot_eval
from pytest_skill_engineering.copilot.personas import (
    ClaudeCodePersona,
    CopilotCLIPersona,
    HeadlessPersona,
    Persona,
    VSCodePersona,
)
from pytest_skill_engineering.copilot.result import CopilotResult
from pytest_skill_engineering.copilot.runner import run_copilot

# TODO(Verbal): optimizer.py (InstructionSuggestion, optimize_instruction) was removed
# This was PydanticAI-based and needs to be rewritten for Copilot SDK or removed
# from pytest_skill_engineering.execution.optimizer import (
#     InstructionSuggestion, optimize_instruction
# )

__all__ = [
    "CopilotEval",
    "CopilotResult",
    # "InstructionSuggestion",  # TODO(Verbal): Removed with optimizer.py
    "ClaudeCodePersona",
    "CopilotCLIPersona",
    "HeadlessPersona",
    "Persona",
    "VSCodePersona",
    "copilot_eval",
    "load_custom_agent",
    "load_custom_agents",
    "load_mcp_config",
    # "optimize_instruction",  # TODO(Verbal): Removed with optimizer.py
    "run_copilot",
]
