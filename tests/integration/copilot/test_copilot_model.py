"""Integration tests for CopilotModel — using the Copilot SDK as a PydanticAI model provider.

Tests that the ``copilot/`` model prefix routes through the Copilot SDK
for ALL auxiliary LLM call sites: text generation, structured output,
llm_assert, llm_score, clarification detection, insights, and optimizer.

These tests require:
- ``pytest-aitest[copilot]`` installed
- Copilot authentication (``gh auth login`` or ``GITHUB_TOKEN``)
"""

from __future__ import annotations

import base64

import pytest

from pytest_aitest.copilot.model import CopilotModel
from pytest_aitest.execution.pydantic_adapter import build_model_from_string

# ---------------------------------------------------------------------------
# Core model functionality
# ---------------------------------------------------------------------------


@pytest.mark.copilot
class TestCopilotModelText:
    """CopilotModel handles plain text LLM calls."""

    async def test_simple_text_response(self) -> None:
        """CopilotModel can answer a simple question."""
        from pydantic_ai import Agent

        agent = Agent(CopilotModel("gpt-5-mini"))
        result = await agent.run("What is 2 + 2? Answer with just the number.")
        assert "4" in result.output

    async def test_build_model_from_string_prefix(self) -> None:
        """The copilot/ prefix in build_model_from_string returns a CopilotModel."""
        model = build_model_from_string("copilot/gpt-5-mini")
        assert isinstance(model, CopilotModel)
        assert model.model_name == "copilot:gpt-5-mini"

        # Verify it actually works end-to-end
        from pydantic_ai import Agent

        agent = Agent(model)
        result = await agent.run("Say hello in exactly one word.")
        assert result.output.strip()


@pytest.mark.copilot
class TestCopilotModelStructuredOutput:
    """CopilotModel returns structured output via tool calling."""

    async def test_structured_output(self) -> None:
        """CopilotModel extracts typed BaseModel output."""
        from pydantic import BaseModel
        from pydantic_ai import Agent

        class MathResult(BaseModel):
            answer: int
            explanation: str

        agent = Agent(CopilotModel("gpt-5-mini"), output_type=MathResult)
        result = await agent.run("What is 15 + 27?")
        assert result.output.answer == 42
        assert result.output.explanation  # Non-empty


# ---------------------------------------------------------------------------
# Auxiliary LLM call sites — each uses build_model_from_string("copilot/...")
# ---------------------------------------------------------------------------


@pytest.mark.copilot
class TestCopilotModelLlmAssert:
    """llm_assert works with CopilotModel as the judge."""

    async def test_llm_assert_passes(self) -> None:
        """judge_output correctly evaluates content via CopilotModel."""
        from pydantic_evals.evaluators.llm_as_a_judge import judge_output

        model = build_model_from_string("copilot/gpt-5-mini")
        grading = await judge_output(
            output="Your checking account balance is $1,500.00",
            rubric="mentions a dollar amount",
            model=model,
        )
        assert grading.pass_
        assert grading.reason

    async def test_llm_assert_fails(self) -> None:
        """judge_output correctly rejects content that doesn't match."""
        from pydantic_evals.evaluators.llm_as_a_judge import judge_output

        model = build_model_from_string("copilot/gpt-5-mini")
        grading = await judge_output(
            output="The weather is sunny today.",
            rubric="mentions a bank account balance",
            model=model,
        )
        assert not grading.pass_


@pytest.mark.copilot
class TestCopilotModelLlmScore:
    """llm_score works with CopilotModel for multi-dimension scoring."""

    async def test_llm_score_rubric(self) -> None:
        """llm_score returns structured scores via CopilotModel."""
        from pytest_aitest.fixtures.llm_score import LLMScore, ScoringDimension

        model = build_model_from_string("copilot/gpt-5-mini")
        scorer = LLMScore(model=model)

        rubric = [
            ScoringDimension("accuracy", "Factually correct information", max_score=5),
            ScoringDimension("clarity", "Clear and easy to understand", max_score=5),
        ]
        result = await scorer.async_score(
            "Python is a high-level, interpreted programming language created by "
            "Guido van Rossum in 1991. It emphasizes code readability and supports "
            "multiple programming paradigms.",
            rubric,
        )
        assert result.total > 0
        assert result.max_total == 10
        assert "accuracy" in result.scores
        assert "clarity" in result.scores
        assert result.weighted_score > 0.0
        assert result.reasoning


@pytest.mark.copilot
class TestCopilotModelLlmAssertImage:
    """llm_assert_image works with CopilotModel as the vision judge."""

    async def test_llm_assert_image_executes(self) -> None:
        """Vision assertion path executes with copilot/ model without errors."""
        from pytest_aitest.fixtures.llm_assert_image import LLMAssertImage

        # 1x1 transparent PNG
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5W3v8AAAAASUVORK5CYII="
        )
        model = build_model_from_string("copilot/gpt-5-mini")
        judge = LLMAssertImage(model=model)

        result = judge(png_bytes, "is an image")
        assert isinstance(result.passed, bool)
        assert result.reasoning


@pytest.mark.copilot
class TestCopilotModelClarification:
    """Clarification detection works with CopilotModel as judge."""

    async def test_detects_clarification(self) -> None:
        """CopilotModel correctly detects a clarification question."""
        from pytest_aitest.execution.clarification import check_clarification

        model = build_model_from_string("copilot/gpt-5-mini")
        is_clarification = await check_clarification(
            "Would you like me to transfer $100 to your savings account? "
            "I want to make sure before proceeding.",
            judge_model=model,
            timeout_seconds=30.0,
        )
        assert is_clarification is True

    async def test_no_clarification(self) -> None:
        """CopilotModel correctly identifies a completed action."""
        from pytest_aitest.execution.clarification import check_clarification

        model = build_model_from_string("copilot/gpt-5-mini")
        is_clarification = await check_clarification(
            "Done! I transferred $100 from checking to savings. "
            "Your new checking balance is $1,400.",
            judge_model=model,
        )
        assert is_clarification is False


@pytest.mark.copilot
class TestCopilotModelInsights:
    """AI insights generation works with CopilotModel."""

    async def test_generate_insights(self) -> None:
        """generate_insights produces a summary via CopilotModel."""
        from pytest_aitest.reporting.collector import build_suite_report
        from pytest_aitest.reporting.insights import generate_insights

        suite = build_suite_report([], name="copilot-model-test")
        insights = await generate_insights(suite, model="copilot/gpt-5-mini")
        assert insights.markdown_summary
        assert len(insights.markdown_summary) > 50


@pytest.mark.copilot
class TestCopilotModelOptimizer:
    """Instruction optimizer works with CopilotModel."""

    async def test_optimize_instruction(self) -> None:
        """optimize_instruction returns a suggestion via CopilotModel."""
        from pytest_aitest.core.result import AgentResult, Turn
        from pytest_aitest.execution.optimizer import optimize_instruction

        # Build a minimal AgentResult representing a failed test
        result = AgentResult(
            turns=[
                Turn(
                    role="user",
                    content="Add docstrings to all functions",
                ),
                Turn(
                    role="assistant",
                    content="I refactored the code and added type hints.",
                ),
            ],
            success=False,
        )

        suggestion = await optimize_instruction(
            "You are a Python developer.",
            result,
            "Agent should add docstrings to all functions, not just type hints.",
            model="copilot/gpt-5-mini",
        )
        assert suggestion.instruction
        assert suggestion.reasoning
        assert suggestion.changes
