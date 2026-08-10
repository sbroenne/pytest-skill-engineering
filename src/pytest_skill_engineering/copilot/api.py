"""Typed public entry points for Copilot execution."""

from __future__ import annotations

from typing import cast

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.result import CopilotResult
from pytest_skill_engineering.copilot.runner import run_copilot as _run_copilot


async def run_copilot(agent: CopilotEval, prompt: str) -> CopilotResult:
    """Execute a prompt and return the concrete public result type."""
    return cast(CopilotResult, await _run_copilot(agent, prompt))
