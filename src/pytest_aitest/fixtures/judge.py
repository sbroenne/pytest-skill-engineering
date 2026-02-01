"""Judge fixture for semantic assertions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_llm_assert import LLMAssert


@pytest.fixture
def judge(request: pytest.FixtureRequest) -> LLMAssert:
    """Fixture providing an LLM judge for semantic assertions.

    The judge can be used to make LLM-powered assertions on any content,
    including agent responses, API outputs, or any other text.

    Uses pytest-llm-assert under the hood for powerful semantic assertions.

    Configuration:
        Model is set via --aitest-model (default: azure/gpt-5-mini).
        Authentication via LiteLLM standard env vars (AZURE_API_BASE, etc.).

    Example:
        def test_response_quality(judge, aitest_run):
            result = await aitest_run(agent, "What is Python?")
            assert judge(result.final_response, "Explains Python programming language")
            assert judge.score(result.final_response, "clarity") >= 0.8

        def test_multiple_criteria(judge, aitest_run):
            result = await aitest_run(agent, "Explain recursion")
            assert judge(result.final_response, '''
                - Defines recursion correctly
                - Provides an example
                - Mentions base case
            ''')
    """
    from pytest_llm_assert import LLMAssert

    model = request.config.getoption("--aitest-model") or "azure/gpt-5-mini"

    # pytest-llm-assert uses LiteLLM internally, so it reads
    # AZURE_API_BASE, OPENAI_API_KEY, etc. from environment
    return LLMAssert(model=model)
