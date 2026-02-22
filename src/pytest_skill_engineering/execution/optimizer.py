"""Instruction optimizer for test-driven prompt engineering.

Provides :func:`optimize_instruction`, which uses an LLM to analyze the gap
between a current agent instruction and the observed behavior, and suggests a
concrete improvement.

Model strings follow the same ``provider/model`` format used by
``pytest-skill-engineering`` (e.g. ``"azure/gpt-5.2-chat"``, ``"openai/gpt-4o-mini"``).
Azure Entra ID authentication is handled automatically when
``AZURE_API_BASE`` or ``AZURE_OPENAI_ENDPOINT`` is set.

Example::

    suggestion = await optimize_instruction(
        agent.system_prompt or "",
        result,
        "Agent should add docstrings.",
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models import Model

from pytest_skill_engineering.execution.pydantic_adapter import build_model_from_string

if TYPE_CHECKING:
    from pytest_skill_engineering.core.result import AgentResult

__all__ = ["InstructionSuggestion", "optimize_instruction"]


@dataclass
class InstructionSuggestion:
    """A suggested improvement to an agent instruction.

    Returned by :func:`optimize_instruction`. Designed to drop into
    ``pytest.fail()`` so the failure message includes an actionable fix.

    Attributes:
        instruction: The improved instruction text to use instead.
        reasoning: Explanation of why this change would close the gap.
        changes: Short description of what was changed (one sentence).

    Example::

        suggestion = await optimize_instruction(
            agent.system_prompt or "",
            result,
            "Agent should add docstrings to all functions.",
        )
        pytest.fail(f"No docstrings found.\\n\\n{suggestion}")
    """

    instruction: str
    reasoning: str
    changes: str

    def __str__(self) -> str:
        return (
            f"💡 Suggested instruction:\n\n"
            f"  {self.instruction}\n\n"
            f"  Changes: {self.changes}\n"
            f"  Reasoning: {self.reasoning}"
        )


class _OptimizationOutput(BaseModel):
    """Structured output schema for the optimizer LLM call."""

    instruction: str
    reasoning: str
    changes: str


async def optimize_instruction(
    current_instruction: str,
    result: AgentResult,
    criterion: str,
    *,
    model: str | Model = "azure/gpt-5.2-chat",
) -> InstructionSuggestion:
    """Analyze a result and suggest an improved instruction.

    Uses pydantic-ai structured output to analyze the gap between a
    current instruction and the agent's observed behavior, returning a
    concrete, actionable improvement.

    Designed to drop into ``pytest.fail()`` so the failure message
    contains a ready-to-use fix.

    Model strings follow the same ``provider/model`` format used by
    ``pytest-skill-engineering``. Azure Entra ID auth is handled automatically
    when ``AZURE_API_BASE`` or ``AZURE_OPENAI_ENDPOINT`` is set.

    Example::

        result = await aitest_run(agent, task)
        if '\"\"\"' not in result.file("main.py"):
            suggestion = await optimize_instruction(
                agent.system_prompt or "",
                result,
                "Agent should add docstrings to all functions.",
            )
            pytest.fail(f"No docstrings found.\\n\\n{suggestion}")

    Args:
        current_instruction: The agent's current instruction / system prompt text.
        result: The :class:`~pytest_skill_engineering.core.result.AgentResult` from the
            (failed) run.
        criterion: What the agent *should* have done — the test expectation
            in plain English (e.g. ``"Always write docstrings"``).
        model: Provider/model string (e.g. ``"azure/gpt-5.2-chat"``,
            ``"openai/gpt-4o-mini"``) or a pre-configured pydantic-ai
            ``Model`` object. Defaults to ``"azure/gpt-5.2-chat"``.

    Returns:
        An :class:`InstructionSuggestion` with the improved instruction.
    """
    resolved_model: str | Model = (
        build_model_from_string(model) if isinstance(model, str) else model
    )
    final_output = result.final_response or "(no response)"
    tool_calls = ", ".join(sorted(result.tool_names_called)) or "none"

    prompt = f"""You are helping improve an AI agent instruction.

## Current instruction
{current_instruction or "(no instruction)"}

## Task the agent performed
{criterion}

## What actually happened
The agent produced:
{final_output[:1500]}

Tools called: {tool_calls}
Run succeeded: {result.success}

## Expected criterion
The agent SHOULD have satisfied this criterion:
{criterion}

Analyze the gap between the instruction and the observed behaviour.
Suggest a specific, concise, directive improvement to the instruction
that would make the agent satisfy the criterion.
Keep the instruction under 200 words. Do not add unrelated rules."""

    optimizer_agent = PydanticAgent(resolved_model, output_type=_OptimizationOutput)
    run_result = await optimizer_agent.run(prompt)
    output = run_result.output

    return InstructionSuggestion(
        instruction=output.instruction,
        reasoning=output.reasoning,
        changes=output.changes,
    )
