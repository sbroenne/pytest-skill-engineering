"""Pytest fixtures for GitHub Copilot testing.

Provides the ``copilot_eval`` fixture that executes prompts against Copilot
and stashes results for pytest-skill-engineering reporting.

Also provides ``ab_run``, a higher-level fixture for A/B testing two agent
configurations against the same task in isolated directories.
"""

from __future__ import annotations

import dataclasses
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pytest

from pytest_skill_engineering.copilot.api import run_copilot

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from _pytest.nodes import Item

    from pytest_skill_engineering.copilot.eval import CopilotEval
    from pytest_skill_engineering.copilot.result import CopilotResult


@pytest.fixture
def copilot_eval(
    request: pytest.FixtureRequest,
) -> Callable[..., Coroutine[Any, Any, CopilotResult]]:
    """Execute a prompt against a CopilotEval and capture results.

    Results are automatically stashed on the test node for pytest-skill-engineering's
    evidence collector. Native JSON preserves execution alongside ordinary pytest
    outcomes; the coding agent interprets it together with source and test criteria.

    Example:
        async def test_file_creation(copilot_eval, tmp_path):
            agent = CopilotEval(
                instructions="Create files as requested.",
                working_directory=str(tmp_path),
            )
            result = await copilot_eval(agent, "Create hello.py with print('hello')")
            assert result.success
            assert result.tool_was_called("create_file")
    """

    async def _run(agent: CopilotEval, prompt: str) -> CopilotResult:
        result = await run_copilot(agent, prompt)

        # Stash for pytest-skill-engineering's reporting plugin.
        # The plugin hook also does this automatically for tests that
        # call run_copilot() directly, but explicit stashing from the
        # fixture ensures it works even if the hook order changes.
        stash_on_item(request.node, agent, result)

        return result

    return _run


def _convert_to_aitest(
    agent: CopilotEval,
    result: CopilotResult,
) -> tuple[Any, Any] | None:
    """Convert CopilotResult to pytest-skill-engineering types.

    Returns ``(EvalResult, agent_wrapper)`` tuple, or ``None`` if conversion
    fails.

    Since CopilotResult already uses pytest-skill-engineering's Turn and ToolCall types,
    the turns can be passed through directly without rebuilding.

    The agent_wrapper is a simple object with the fields expected by plugin.py:
    - name
    - provider.model
    - system_prompt_name (optional)
    - mcp_servers (optional)
    - allowed_tools (optional)
    """
    from dataclasses import dataclass

    from pytest_skill_engineering.core.result import EvalResult, SubagentInvocation
    from pytest_skill_engineering.execution.cost import estimate_cost

    # Estimate USD cost from captured token usage and pricing.toml.
    # Models without pricing contribute 0.0 and are recorded in
    # execution.cost.models_without_pricing (saved with report evidence).
    cost_usd = sum(
        estimate_cost(
            usage.model or result.model_used or "",
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_tokens or 0,
        )
        for usage in result.all_usage
        if usage.input_tokens is not None and usage.output_tokens is not None
    )

    # Turns already use aitest's Turn/ToolCall types — pass through directly
    aitest_result = EvalResult(
        turns=list(result.turns),
        success=result.success,
        error=result.error,
        duration_ms=result.duration_ms,
        token_usage=result.token_usage,
        cost_usd=cost_usd,
        effective_system_prompt=(
            result.configuration.get("instructions") if result.configuration is not None else None
        ),
        premium_requests=result.total_premium_requests,
        evidence_complete=result.evidence_complete,
        capture_errors=list(result.capture_errors),
        request_audit=list(result.request_audit),
        stop_reason=result.stop_reason,
        usage=list(result.usage),
        tool_calls_admitted=result.tool_calls_admitted,
        skill_discovery=deepcopy(result.skill_discovery),
        configuration=deepcopy(result.configuration),
        model_used=result.model_used,
        reasoning_traces=list(result.reasoning_traces),
        permission_requested=result.permission_requested,
        permissions=deepcopy(result.permissions),
    )
    for invocation in result.subagent_invocations:
        child_result = None
        if invocation.result is not None:
            from pytest_skill_engineering.copilot.eval import CopilotEval

            child_agent = invocation.result.agent
            if not isinstance(child_agent, CopilotEval):
                raise ValueError(f"Child invocation {invocation.invocation_id!r} has no eval")
            converted_child = _convert_to_aitest(child_agent, invocation.result)
            assert converted_child is not None
            child_result = converted_child[0]
        aitest_result.subagent_invocations.append(
            SubagentInvocation(
                invocation_id=invocation.invocation_id,
                name=invocation.name,
                status=invocation.status,
                duration_ms=invocation.duration_ms,
                result=child_result,
            )
        )

    # Create a minimal wrapper with just the fields needed by plugin.py
    @dataclass(slots=True)
    class Provider:
        model: str | None

    @dataclass(slots=True)
    class AgentWrapper:
        name: str
        id: str
        provider: Provider
        system_prompt_name: str | None = None
        mcp_servers: list[Any] = None  # type: ignore[assignment]
        allowed_tools: list[str] | None = None
        skill: Any = None

        def __post_init__(self) -> None:
            if self.mcp_servers is None:
                self.mcp_servers = []

    aitest_agent = AgentWrapper(
        name=agent.name,
        id=agent.name,
        provider=Provider(
            model=result.model_used
            if result.model_used is not None
            else (
                result.configuration.get("model")
                if result.configuration is not None
                else agent.extra_config.get("model", agent.model)
            )
        ),
        system_prompt_name=None,  # CopilotEval doesn't have named prompts
        mcp_servers=[],  # Could convert agent.mcp_servers if needed
        allowed_tools=agent.allowed_tools,
    )

    return aitest_result, aitest_agent


def stash_on_item(
    item: Item,
    agent: CopilotEval,
    result: CopilotResult,
    *,
    comparison_role: Literal["baseline", "treatment"] | None = None,
) -> None:
    """Stash result on the test node for pytest-skill-engineering compatibility.

    The plugin reads ``node._aitest_runs`` to retain every execution.
    ``node._aitest_result`` and ``node._aitest_agent`` expose the latest
    execution for other report hooks.

    ``comparison_role`` labels report records only; the runtime config and
    result's agent back-reference remain unchanged.

    Called automatically by the ``copilot_eval`` fixture and by the
    ``pytest_runtest_makereport`` plugin hook; consumers should rarely
    need to call this directly.
    """
    converted = _convert_to_aitest(agent, result)
    if converted is not None:
        if comparison_role is not None:
            report_name = f"{agent.name} ({comparison_role})"
            converted[1].name = report_name
            converted[1].id = report_name
            converted[0].comparison_role = comparison_role
        item._aitest_result = converted[0]  # type: ignore[attr-defined]
        item._aitest_agent = converted[1]  # type: ignore[attr-defined]
        runs = getattr(item, "_aitest_runs", None)
        if runs is None:
            runs = []
            item._aitest_runs = runs  # type: ignore[attr-defined]
        runs.append(converted)


def _prepare_ab_configs(
    baseline: CopilotEval, treatment: CopilotEval, tmp_path: Path
) -> tuple[CopilotEval, CopilotEval]:
    baseline_dir = tmp_path / "baseline"
    treatment_dir = tmp_path / "treatment"
    baseline_dir.mkdir(exist_ok=True)
    treatment_dir.mkdir(exist_ok=True)
    return (
        dataclasses.replace(baseline, working_directory=str(baseline_dir)),
        dataclasses.replace(treatment, working_directory=str(treatment_dir)),
    )


@pytest.fixture
def ab_run(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> Callable[..., Coroutine[Any, Any, tuple[CopilotResult, CopilotResult]]]:
    """Run two agents against the same task in isolated directories.

    Creates ``baseline/`` and ``treatment/`` subdirectories under
    ``tmp_path``, overrides ``working_directory`` on each agent so they
    never share a workspace, then runs them sequentially and stashes
    both results for pytest-skill-engineering reporting. Each side keeps its
    configuration and trace; the pytest outcome describes the combined test.

    Example::

        async def test_docstring_instruction(ab_run):
            baseline = CopilotEval(instructions="Write Python code.")
            treatment = CopilotEval(
                instructions="Write Python code. Add Google-style docstrings to every function."
            )

            b, t = await ab_run(baseline, treatment, "Create math.py with add(a, b).")

            assert b.success and t.success
            assert '\"\"\"' not in b.file("math.py"), "Baseline should not have docstrings"
            assert '\"\"\"' in t.file("math.py"), "Treatment should add docstrings"

    Args:
        baseline: Control ``CopilotEval`` (the existing / unchanged config).
        treatment: Treatment ``CopilotEval`` (the change you are testing).
        task: Prompt to give both agents.

    Returns:
        ``(baseline_result, treatment_result)`` tuple.
    """

    async def _run(
        baseline: CopilotEval,
        treatment: CopilotEval,
        task: str,
    ) -> tuple[CopilotResult, CopilotResult]:
        baseline, treatment = _prepare_ab_configs(baseline, treatment, tmp_path)

        # Run sequentially — agents may write to disk, install packages, etc.
        baseline_result = await run_copilot(baseline, task)
        stash_on_item(request.node, baseline, baseline_result, comparison_role="baseline")
        treatment_result = await run_copilot(treatment, task)

        stash_on_item(request.node, treatment, treatment_result, comparison_role="treatment")

        return baseline_result, treatment_result

    return _run
