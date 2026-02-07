"""Two agents compared side-by-side.

Tests leaderboard and comparison view. No agent selector (requires 3+).

Generates: tests/fixtures/reports/02_multi_agent.json

Run:
    pytest tests/fixtures/scenario_02_multi_agent.py -v \
        --aitest-json=tests/fixtures/reports/02_multi_agent.json
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

AGENTS = [
    Agent(
        name="gpt-5-mini",
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[weather_server],
        system_prompt=WEATHER_PROMPT,
        max_turns=5,
    ),
    Agent(
        name="gpt-4.1-mini",
        provider=Provider(model="azure/gpt-4.1-mini", rpm=10, tpm=10000),
        mcp_servers=[weather_server],
        system_prompt=WEATHER_PROMPT,
        max_turns=5,
    ),
]


@pytest.fixture(autouse=True)
def _reset_agents():
    """Reset mutable agent state after each test."""
    yield
    for a in AGENTS:
        a.max_turns = 5


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_simple_weather(aitest_run, agent, llm_assert):
    """Basic weather query — all agents should pass."""
    result = await aitest_run(agent, "What's the weather in London?")
    assert result.success
    assert result.tool_was_called("get_weather")
    assert result.tool_call_arg("get_weather", "city") == "London"
    assert llm_assert(result.final_response, "describes the current weather conditions")


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_forecast(aitest_run, agent, llm_assert):
    """Forecast query — tests tool selection."""
    result = await aitest_run(agent, "5-day forecast for New York please")
    assert result.success
    assert result.tool_was_called("get_forecast")
    assert result.tool_call_arg("get_forecast", "city") == "New York"
    assert result.tool_call_count("get_forecast") >= 1
    assert llm_assert(result.final_response, "provides a 5-day forecast with daily conditions")
    assert result.duration_ms < 30000


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_comparison(aitest_run, agent, llm_assert):
    """City comparison — multi-step reasoning."""
    agent.max_turns = 8
    result = await aitest_run(
        agent, "Compare Paris and Tokyo weather - which is better for a picnic?"
    )
    assert result.success
    assert result.tool_call_count("get_weather") >= 2 or result.tool_was_called("compare_weather")
    if result.tool_was_called("compare_weather"):
        assert result.tool_call_arg("compare_weather", "city1") in {"Paris", "Tokyo"}
        assert result.tool_call_arg("compare_weather", "city2") in {"Paris", "Tokyo"}
    else:
        cities = {call.arguments.get("city") for call in result.tool_calls_for("get_weather")}
        assert {"Paris", "Tokyo"}.issubset(cities)
    assert llm_assert(
        result.final_response,
        "recommends which city is better for a picnic based on weather",
    )
