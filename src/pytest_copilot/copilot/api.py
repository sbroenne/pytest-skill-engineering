"""Typed public entry points for Copilot execution."""

from __future__ import annotations

from pytest_copilot.copilot.result import CopilotResult
from pytest_copilot.copilot.runner import run_copilot as _run_copilot
from pytest_copilot.copilot.task import CopilotTask


async def run_copilot(agent: CopilotTask, prompt: str) -> CopilotResult:
    """Execute a prompt and return the concrete public result type."""
    return await _run_copilot(agent, prompt)
