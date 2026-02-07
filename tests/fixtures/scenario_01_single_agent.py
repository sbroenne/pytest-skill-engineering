"""Single agent tests - basic report without comparison UI.

Tests pass/fail, assertions, tool calls, mermaid diagrams.

Generates: tests/fixtures/reports/01_single_agent.json

Run:
    pytest tests/fixtures/scenario_01_single_agent.py -v \
        --aitest-json=tests/fixtures/reports/01_single_agent.json
"""

from __future__ import annotations

import sys

import pytest

from pytest_aitest import Agent, MCPServer, Provider, Wait

pytestmark = [pytest.mark.integration]

WEATHER_PROMPT = """You are a helpful weather assistant.
Use the available tools to answer questions about weather.
Always use tools - never make up weather data."""

weather_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_aitest.testing.weather_mcp"],
    wait=Wait.for_tools(["get_weather", "get_forecast", "list_cities"]),
)

agent = Agent(
    name="weather-agent",
    provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
    mcp_servers=[weather_server],
    system_prompt=WEATHER_PROMPT,
    max_turns=5,
)


@pytest.fixture(autouse=True)
def _reset_agent():
    """Reset mutable agent state after each test."""
    yield
    agent.max_turns = 5


async def test_simple_weather_query(aitest_run, llm_assert):
    """Basic weather lookup — should pass."""
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
    assert result.tool_was_called("get_weather")
    assert result.tool_call_arg("get_weather", "city") == "Paris"
    assert llm_assert(result.final_response, "mentions the temperature in Celsius or Fahrenheit")
    assert result.cost_usd < 0.05


async def test_forecast_query(aitest_run, llm_assert):
    """Multi-day forecast — tests get_forecast tool."""
    result = await aitest_run(agent, "Give me a 3-day forecast for Tokyo")
    assert result.success
    assert result.tool_was_called("get_forecast")
    assert result.tool_call_arg("get_forecast", "city") == "Tokyo"
    assert llm_assert(result.final_response, "provides weather information for multiple days")


async def test_city_comparison(aitest_run, llm_assert):
    """Compare two cities — multiple tool calls."""
    agent.max_turns = 8
    result = await aitest_run(agent, "Which is warmer today, Berlin or Sydney?")
    assert result.success
    assert result.tool_call_count("get_weather") >= 2 or result.tool_was_called("compare_weather")
    if result.tool_was_called("compare_weather"):
        assert result.tool_call_arg("compare_weather", "city1") in {"Berlin", "Sydney"}
        assert result.tool_call_arg("compare_weather", "city2") in {"Berlin", "Sydney"}
    else:
        cities = {call.arguments.get("city") for call in result.tool_calls_for("get_weather")}
        assert {"Berlin", "Sydney"}.issubset(cities)
    assert llm_assert(result.final_response, "compares temperatures for both cities")


async def test_expected_failure(aitest_run):
    """Test that fails due to turn limit — for report variety."""
    agent.max_turns = 1
    result = await aitest_run(
        agent, "Get weather for Paris, Tokyo, London, Berlin, Sydney, and compare them all"
    )
    # Intentional failure to demonstrate error display in reports
    raise AssertionError(
        "Agent exceeded turn limit - unable to process request for 5 cities (max_turns=1)"
    )
