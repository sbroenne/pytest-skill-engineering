"""LLM-powered semantic assertion fixture.

Provides the ``llm_assert`` fixture for evaluating text content against
plain-English criteria using pydantic-evals' LLM judge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pydantic_ai.models import Model

_LLM_MODEL_DEFAULT = "openai/gpt-5-mini"


@dataclass(slots=True)
class AssertionResult:
    """Result of an LLM assertion with rich repr for pytest."""

    passed: bool
    criterion: str
    reasoning: str
    content_preview: str

    def __bool__(self) -> bool:
        return self.passed

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"LLMAssert({status}: {self.criterion!r})\n"
            f"  Content: {self.content_preview!r}\n"
            f"  Reasoning: {self.reasoning}"
        )


class LLMAssert:
    """Callable that evaluates content against criteria using an LLM judge.

    Uses ``pydantic_evals.evaluators.llm_as_a_judge.judge_output()`` for
    structured rubric-based evaluation.

    Example::

        def test_greeting(llm_assert):
            response = "Hello! How can I help you today?"
            assert llm_assert(response, "Is this a friendly greeting?")
    """

    def __init__(self, model: Model | str) -> None:
        self._model = model

    def __call__(self, content: str, criterion: str) -> AssertionResult:
        """Evaluate if content meets the given criterion.

        Args:
            content: The text to evaluate.
            criterion: Plain English criterion (e.g., "mentions account balance").

        Returns:
            AssertionResult that is truthy if criterion is met.
        """
        import asyncio
        import concurrent.futures

        from pydantic_evals.evaluators.llm_as_a_judge import judge_output

        async def _judge() -> Any:
            return await judge_output(
                output=content,
                rubric=criterion,
                model=self._model,
            )

        # judge_output is async, but llm_assert is called synchronously
        # (often from inside an already-running event loop in async tests).
        # Run in a new thread with its own event loop.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            grading = pool.submit(asyncio.run, _judge()).result()

        preview = content[:200] + "..." if len(content) > 200 else content

        return AssertionResult(
            passed=grading.pass_,
            criterion=criterion,
            reasoning=grading.reason,
            content_preview=preview,
        )


def _build_judge_model(model_str: str) -> Any:
    """Build a PydanticAI model from a model string for the judge."""
    from pytest_skill_engineering.execution.pydantic_adapter import build_model_from_string

    return build_model_from_string(model_str)


@pytest.fixture
def llm_assert(request: pytest.FixtureRequest) -> LLMAssert:
    """Fixture providing LLM-powered semantic assertions.

    The judge model is resolved in this order:
    1. ``--llm-model`` if explicitly set
    2. ``--aitest-summary-model`` (same model for analysis and assertions)
    3. ``openai/gpt-5-mini`` as final fallback

    Example::

        def test_response(llm_assert):
            assert llm_assert("Your balance is $1,500", "mentions a dollar amount")
    """
    model_str: str = request.config.getoption("--llm-model")
    if model_str == _LLM_MODEL_DEFAULT:
        # Not explicitly set — fall back to summary model if available
        summary_model = request.config.getoption("--aitest-summary-model", default=None)
        if summary_model:
            model_str = summary_model
    model = _build_judge_model(model_str)
    return LLMAssert(model=model)
