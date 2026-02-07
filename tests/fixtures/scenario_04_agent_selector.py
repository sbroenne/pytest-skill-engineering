"""Three agents for testing the agent selector UI.

Agent selector only appears when there are 3+ agents.

Generates: tests/fixtures/reports/04_agent_selector.json

Run:
    pytest tests/fixtures/scenario_04_agent_selector.py -v \
        --aitest-json=tests/fixtures/reports/04_agent_selector.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_aitest import Agent, MCPServer, Provider, Skill, Wait

pytestmark = [pytest.mark.integration]

WEATHER_PROMPT = """You are a helpful weather assistant.
Use the available tools to answer questions about weather.
Always use tools - never make up weather data."""

weather_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_aitest.testing.weather_mcp"],
    wait=Wait.for_tools(["get_weather", "get_forecast", "list_cities"]),
)

# Load skill for agent variation
SKILLS_DIR = Path(__file__).parent.parent / "integration" / "skills"
WEATHER_SKILL = (
    Skill.from_path(SKILLS_DIR / "weather-expert")
    if (SKILLS_DIR / "weather-expert").exists()
    else None
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
    Agent(
        name="gpt-5-mini+skill",
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[weather_server],
        system_prompt=WEATHER_PROMPT,
        skill=WEATHER_SKILL,
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
async def test_weather_query(aitest_run, agent, llm_assert):
    """Basic weather query — all agents should pass."""
    result = await aitest_run(agent, "What's the weather in Berlin?")
    assert result.success
    assert result.tool_was_called("get_weather")
    assert result.tool_call_arg("get_weather", "city") == "Berlin"
    assert llm_assert(
        result.final_response,
        "provides the current temperature and conditions for Berlin",
    )


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_multi_city(aitest_run, agent, llm_assert):
    """Multiple cities — tests differentiation between agents."""
    agent.max_turns = 8
    result = await aitest_run(agent, "Compare weather in Rome, Madrid, and Athens")
    assert result.success
    assert result.tool_call_count("get_weather") >= 3
    assert llm_assert(result.final_response, "mentions weather for Rome, Madrid, and Athens")
