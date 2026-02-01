"""pytest hooks for aitest reporting and extensibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_aitest.config import Agent
    from pytest_aitest.result import AgentResult


# Hook specifications for pytest-aitest extensibility
class AitestHookSpec:
    """Hook specifications for pytest-aitest plugins."""

    @pytest.hookspec(firstresult=True)
    def pytest_aitest_before_run(self, agent: Agent, prompt: str) -> Agent | None:
        """Called before running an agent.

        Can modify the agent configuration or return None to use as-is.

        Args:
            agent: The agent configuration
            prompt: The user prompt

        Returns:
            Modified Agent or None
        """
        ...

    @pytest.hookspec
    def pytest_aitest_after_run(self, agent: Agent, prompt: str, result: AgentResult) -> None:
        """Called after running an agent.

        Can be used for logging, metrics collection, etc.

        Args:
            agent: The agent configuration
            prompt: The user prompt
            result: The agent execution result
        """
        ...

    @pytest.hookspec
    def pytest_aitest_tool_called(
        self, tool_name: str, arguments: dict, result: str | None, error: str | None
    ) -> None:
        """Called after each tool call.

        Args:
            tool_name: Name of the tool that was called
            arguments: Arguments passed to the tool
            result: Tool result (if successful)
            error: Error message (if failed)
        """
        ...

    @pytest.hookspec(firstresult=True)
    def pytest_aitest_judge_prompt(self, content: str, criterion: str) -> str | None:
        """Customize the judge evaluation prompt.

        Args:
            content: Content being evaluated
            criterion: Evaluation criterion

        Returns:
            Custom prompt or None to use default
        """
        ...
