"""Pytest fixtures for GitHub Copilot testing.

Provides the ``copilot_run`` fixture that executes prompts against Copilot
and stashes results for pytest-skill-engineering reporting.

Also provides ``ab_run``, a higher-level fixture for A/B testing two agent
configurations against the same task in isolated directories.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_skill_engineering.copilot.runner import run_copilot

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from _pytest.nodes import Item

    from pytest_skill_engineering.copilot.agent import CopilotAgent
    from pytest_skill_engineering.copilot.result import CopilotResult


@pytest.fixture
def copilot_run(
    request: pytest.FixtureRequest,
) -> Callable[..., Coroutine[Any, Any, CopilotResult]]:
    """Execute a prompt against a CopilotAgent and capture results.

    Results are automatically stashed on the test node for pytest-skill-engineering's
    reporting plugin. This gives you full HTML reports —
    leaderboard, AI insights, Mermaid diagrams — for free.

    Example:
        async def test_file_creation(copilot_run, tmp_path):
            agent = CopilotAgent(
                instructions="Create files as requested.",
                working_directory=str(tmp_path),
            )
            result = await copilot_run(agent, "Create hello.py with print('hello')")
            assert result.success
            assert result.tool_was_called("create_file")
    """

    async def _run(agent: CopilotAgent, prompt: str) -> CopilotResult:
        result = await run_copilot(agent, prompt)

        # Stash for pytest-skill-engineering's reporting plugin.
        # The plugin hook also does this automatically for tests that
        # call run_copilot() directly, but explicit stashing from the
        # fixture ensures it works even if the hook order changes.
        stash_on_item(request.node, agent, result)

        return result

    return _run


def _convert_to_aitest(
    agent: CopilotAgent,
    result: CopilotResult,
) -> tuple[Any, Any] | None:
    """Convert CopilotResult to pytest-skill-engineering types.

    Returns ``(AgentResult, Agent)`` tuple, or ``None`` if conversion
    fails.

    Since CopilotResult already uses pytest-skill-engineering's Turn and ToolCall types,
    the turns can be passed through directly without rebuilding.
    """
    from pytest_skill_engineering.core.agent import Agent, Provider
    from pytest_skill_engineering.core.result import AgentResult

    # Turns already use aitest's Turn/ToolCall types — pass through directly
    aitest_result = AgentResult(
        turns=list(result.turns),
        success=result.success,
        error=result.error,
        duration_ms=result.duration_ms,
        token_usage=result.token_usage,
        cost_usd=result.cost_usd,
        effective_system_prompt=agent.instructions or "",
    )

    aitest_agent = Agent(
        name=agent.name,
        provider=Provider(model=result.model_used or agent.model or "copilot-default"),
        system_prompt=agent.instructions,
        max_turns=agent.max_turns,
    )

    return aitest_result, aitest_agent


def stash_on_item(
    item: Item,
    agent: CopilotAgent,
    result: CopilotResult,
) -> None:
    """Stash result on the test node for pytest-skill-engineering compatibility.

    pytest-skill-engineering's plugin reads ``node._aitest_result`` and
    ``node._aitest_agent`` in its ``pytest_runtest_makereport`` hook
    to build HTML reports. We produce compatible objects so Copilot
    test results appear in the same reports as synthetic agent tests.

    Called automatically by the ``copilot_run`` fixture and by the
    ``pytest_runtest_makereport`` plugin hook; consumers should rarely
    need to call this directly.
    """
    converted = _convert_to_aitest(agent, result)
    if converted is not None:
        item._aitest_result = converted[0]  # type: ignore[attr-defined]
        item._aitest_agent = converted[1]  # type: ignore[attr-defined]


@pytest.fixture
def ab_run(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Callable[..., Coroutine[Any, Any, tuple[CopilotResult, CopilotResult]]]:
    """Run two agents against the same task in isolated directories.

    Creates ``baseline/`` and ``treatment/`` subdirectories under
    ``tmp_path``, overrides ``working_directory`` on each agent so they
    never share a workspace, then runs them sequentially and stashes the
    treatment result for pytest-skill-engineering reporting.

    Example::

        async def test_docstring_instruction(ab_run):
            baseline = CopilotAgent(instructions="Write Python code.")
            treatment = CopilotAgent(
                instructions="Write Python code. Add Google-style docstrings to every function."
            )

            b, t = await ab_run(baseline, treatment, "Create math.py with add(a, b).")

            assert b.success and t.success
            assert '\"\"\"' not in b.file("math.py"), "Baseline should not have docstrings"
            assert '\"\"\"' in t.file("math.py"), "Treatment should add docstrings"

    Args:
        baseline: Control ``CopilotAgent`` (the existing / unchanged config).
        treatment: Treatment ``CopilotAgent`` (the change you are testing).
        task: Prompt to give both agents.

    Returns:
        ``(baseline_result, treatment_result)`` tuple.
    """

    async def _run(
        baseline: CopilotAgent,
        treatment: CopilotAgent,
        task: str,
    ) -> tuple[CopilotResult, CopilotResult]:
        baseline_dir = tmp_path / "baseline"
        treatment_dir = tmp_path / "treatment"
        baseline_dir.mkdir(exist_ok=True)
        treatment_dir.mkdir(exist_ok=True)

        # Override working directories to guarantee isolation.
        # CopilotAgent is frozen — dataclasses.replace() creates a new instance.
        baseline = dataclasses.replace(baseline, working_directory=str(baseline_dir))
        treatment = dataclasses.replace(treatment, working_directory=str(treatment_dir))

        # Run sequentially — agents may write to disk, install packages, etc.
        baseline_result = await run_copilot(baseline, task)
        treatment_result = await run_copilot(treatment, task)

        # Stash treatment result for pytest-skill-engineering reporting.
        # Treatment is the config being evaluated; its result is what matters.
        stash_on_item(request.node, treatment, treatment_result)

        return baseline_result, treatment_result

    return _run
