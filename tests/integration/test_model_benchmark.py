"""Model benchmark tests - compare multiple LLMs.

Use @pytest.mark.parametrize to run the same test across multiple models.
The report auto-detects this and shows a model comparison table.

Run with: pytest tests/integration/test_model_benchmark.py -v --aitest-html=report.html
"""

from __future__ import annotations

import pytest

from pytest_aitest import Agent, Provider

pytestmark = [pytest.mark.integration, pytest.mark.benchmark]

# Models to benchmark - cheapest first
# Available on Azure: gpt-5-mini, gpt-5.1-chat, gpt-4.1
MODELS = ["gpt-5-mini", "gpt-4.1"]


class TestModelBenchmark:
    """Compare which model works best for weather tasks.

    The report will show:
    - Pass rate per model
    - Token usage per model
    - Cost per model
    """

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.asyncio
    async def test_simple_weather_query(
        self, aitest_run, weather_server, model
    ):
        """Basic weather lookup - all models should pass this."""
        agent = Agent(
            provider=Provider(model=f"azure/{model}"),
            mcp_servers=[weather_server],
            system_prompt="You are a helpful weather assistant.",
            max_turns=5,
        )

        result = await aitest_run(agent, "What's the weather in Paris?")

        assert result.success
        assert result.tool_was_called("get_weather")

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.asyncio
    async def test_multi_city_comparison(
        self, aitest_run, weather_server, model
    ):
        """Compare weather in two cities - tests reasoning."""
        agent = Agent(
            provider=Provider(model=f"azure/{model}"),
            mcp_servers=[weather_server],
            system_prompt="You are a helpful weather assistant.",
            max_turns=5,
        )

        result = await aitest_run(
            agent, "Which is warmer right now, Tokyo or Berlin?"
        )

        assert result.success
        # Must have called weather tools
        assert result.tool_was_called("get_weather") or result.tool_was_called(
            "compare_weather"
        )
        # Response should answer the question
        assert "tokyo" in result.final_response.lower()

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.asyncio
    async def test_forecast_interpretation(
        self, aitest_run, weather_server, model
    ):
        """Forecast + interpretation - tests comprehension."""
        agent = Agent(
            provider=Provider(model=f"azure/{model}"),
            mcp_servers=[weather_server],
            system_prompt="You are a helpful weather assistant. Give practical advice.",
            max_turns=5,
        )

        result = await aitest_run(
            agent, "Should I bring an umbrella to London this week?"
        )

        assert result.success
        # Agent should check forecast or current weather
        assert result.tool_was_called("get_weather") or result.tool_was_called(
            "get_forecast"
        )
