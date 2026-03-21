"""LLM-powered semantic assertion fixture.

Provides the ``llm_assert`` fixture for evaluating text content against
plain-English criteria using the Copilot SDK as an LLM judge.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass

import pytest

_LLM_MODEL_DEFAULT = "copilot/gpt-5-mini"


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

    Uses the Copilot SDK to send a judge prompt and parse the response for
    PASS/FAIL determination.

    Example::

        def test_greeting(llm_assert):
            response = "Hello! How can I help you today?"
            assert llm_assert(response, "Is this a friendly greeting?")
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def __call__(self, content: str, criterion: str) -> AssertionResult:
        """Evaluate if content meets the given criterion.

        Args:
            content: The text to evaluate.
            criterion: Plain English criterion (e.g., "mentions account balance").

        Returns:
            AssertionResult that is truthy if criterion is met.
        """
        from pytest_skill_engineering.copilot.judge import copilot_judge  # noqa: PLC0415

        prompt = (
            f"You are a judge. Evaluate if the following content meets the criterion.\n\n"
            f"Criterion: {criterion}\n\n"
            f"Content:\n---\n{content}\n---\n\n"
            f"Respond with ONLY 'PASS' or 'FAIL' on the first line, "
            f"followed by a brief reasoning on the second line."
        )

        async def _judge() -> tuple[bool, str]:
            # Strip model prefix if present (copilot/, azure/, openai/)
            model = self._model
            if "/" in model:
                model = model.split("/", 1)[1]

            response = await copilot_judge(prompt, model=model, timeout_seconds=30.0)

            # Parse response: first line should be PASS or FAIL
            lines = response.strip().split("\n", 1)
            verdict = lines[0].strip().upper()
            reasoning = lines[1].strip() if len(lines) > 1 else "No reasoning provided"

            # Extract PASS/FAIL from verdict
            passed = "PASS" in verdict and "FAIL" not in verdict

            return passed, reasoning

        # Run in a new thread with its own event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            passed, reasoning = pool.submit(asyncio.run, _judge()).result()

        preview = content[:200] + "..." if len(content) > 200 else content

        return AssertionResult(
            passed=passed,
            criterion=criterion,
            reasoning=reasoning,
            content_preview=preview,
        )


@pytest.fixture
def llm_assert(request: pytest.FixtureRequest) -> LLMAssert:
    """Fixture providing LLM-powered semantic assertions.

    The judge model is resolved in this order:
    1. ``--llm-model`` if explicitly set
    2. ``--aitest-summary-model`` (same model for analysis and assertions)
    3. ``copilot/gpt-5-mini`` as final fallback

    Example::

        def test_response(llm_assert):
            assert llm_assert("Your balance is $1,500", "mentions a dollar amount")
    """
    model_str: str = request.config.getoption("--llm-model")
    if model_str == "openai/gpt-5-mini":  # Old default
        model_str = _LLM_MODEL_DEFAULT
    if model_str == _LLM_MODEL_DEFAULT:
        # Not explicitly set — fall back to summary model if available
        summary_model = request.config.getoption("--aitest-summary-model", default=None)
        if summary_model:
            model_str = summary_model
    return LLMAssert(model=model_str)
