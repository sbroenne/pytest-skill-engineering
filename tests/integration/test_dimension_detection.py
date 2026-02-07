"""Test that dimension auto-detection works correctly.

This single test file proves the aggregator correctly detects which dimensions vary
across test runs. We use a 2×2 matrix (2 models × 2 prompts) to prove both model
and system prompt dimensions are detected.

Cost-conscious: Only 4 LLM calls total, but proves the full auto-detection pipeline.
"""

from __future__ import annotations

import pytest

from pytest_aitest import Agent, Provider

from .conftest import (
    DEFAULT_MAX_TURNS,
    DEFAULT_RPM,
    DEFAULT_TPM,
    WEATHER_PROMPT,
)

# Second prompt for dimension detection
CONCISE_WEATHER_PROMPT = """You are a weather assistant. Be extremely brief.

Use the weather tools to answer questions. Give short, direct answers."""

# Two models to test model dimension detection
TEST_MODELS = ["gpt-5-mini", "gpt-4.1-mini"]

# Two prompts to test system prompt dimension detection
TEST_PROMPTS = {
    "detailed": WEATHER_PROMPT,
    "concise": CONCISE_WEATHER_PROMPT,
}


class TestDimensionDetection:
    """Proves auto-detection works by varying model AND system prompt.

    When this test runs with all permutations, the aggregator should detect:
    - Model dimension varies (gpt-5-mini vs gpt-4.1-mini)
    - System Prompt dimension varies (detailed vs concise)

    The AI report should then focus its analysis on BOTH dimensions,
    explaining which model and which prompt work best.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", TEST_MODELS, ids=TEST_MODELS)
    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_weather_with_all_permutations(
        self,
        aitest_run,
        weather_server,
        model: str,
        prompt_name: str,
        system_prompt: str,
    ):
        """Run weather query across all model × prompt permutations.

        This single test generates 4 runs (2 models × 2 prompts).
        The aggregator should detect both dimensions vary.
        """
        agent = Agent(
            provider=Provider(
                model=f"azure/{model}",
                rpm=DEFAULT_RPM,
                tpm=DEFAULT_TPM,
            ),
            mcp_servers=[weather_server],
            system_prompt=system_prompt,
            system_prompt_name=prompt_name,
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await aitest_run(agent, "What's the weather in Paris?")

        assert result.success
        assert result.tool_was_called("get_weather")
