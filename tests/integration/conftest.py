"""Fixtures for integration tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

# Load .env from workspace root
_env_file = Path(__file__).parents[4] / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

from pytest_aitest import Agent, MCPServer, Provider, Wait

# =============================================================================
# MCP Server Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def weather_server():
    """Weather MCP server - simple "hello world" for testing."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_aitest.testing.weather_mcp",
        ],
        wait=Wait.for_tools(["get_weather", "get_forecast", "list_cities"]),
    )


@pytest.fixture(scope="module")
def todo_server():
    """Todo MCP server - stateful task management."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_aitest.testing.todo_mcp",
        ],
        wait=Wait.for_tools(["add_task", "list_tasks", "complete_task"]),
    )


@pytest.fixture(scope="module")
def test_mcp_server():
    """KeyValue MCP server - for backwards compatibility."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_aitest.testing.mcp_server",
        ],
        wait=Wait.for_tools(["get", "set", "list_keys"]),
    )


# =============================================================================
# Provider Helpers
# =============================================================================


# =============================================================================
# Agent Factories
# =============================================================================


@pytest.fixture
def weather_agent_factory(weather_server, request) -> Callable[..., Agent]:
    """Factory to create agents with the weather server.

    Automatic Azure Entra ID auth - just run `az login`.
    LLM endpoint configured via AZURE_API_BASE env var.

    Example:
        def test_weather(weather_agent_factory):
            agent = weather_agent_factory("gpt-5-mini")
            result = await aitest_run(agent, "What's the weather in Paris?")
    """
    default_prompt = """You are a weather assistant with access to real-time weather tools.

IMPORTANT: Always use the available tools to get weather data. Never guess or use your training data for weather information - it may be outdated. The tools provide current, accurate data.

Available tools:
- get_weather: Get current weather for a city
- get_forecast: Get multi-day forecast for a city
- list_cities: See which cities have weather data
- compare_weather: Compare weather between two cities

When asked about weather, ALWAYS call the appropriate tool first, then respond based on the tool's output."""

    # Get rate limits from CLI options
    rpm = request.config.getoption("--aitest-rpm", default=None)
    tpm = request.config.getoption("--aitest-tpm", default=None)

    def create_agent(
        deployment: str,
        system_prompt: str = default_prompt,
        max_turns: int = 5,
    ) -> Agent:
        return Agent(
            provider=Provider(model=f"azure/{deployment}", rpm=rpm, tpm=tpm),
            mcp_servers=[weather_server],
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
    return create_agent


@pytest.fixture
def todo_agent_factory(todo_server, request) -> Callable[..., Agent]:
    """Factory to create agents with the todo server.

    Automatic Azure Entra ID auth - just run `az login`.
    LLM endpoint configured via AZURE_API_BASE env var.

    Example:
        def test_todo(todo_agent_factory):
            agent = todo_agent_factory("gpt-5-mini")
            result = await aitest_run(agent, "Add buy milk to my shopping list")
    """
    default_prompt = """You are a task management assistant with access to a todo list system.

IMPORTANT: Always use the available tools to manage tasks. The tools are the only way to create, modify, or view tasks.

Available tools:
- add_task: Add a new task (with optional list name and priority)
- complete_task: Mark a task as done (requires task_id)
- list_tasks: View tasks (can filter by list or completion status)
- get_lists: See all available list names
- delete_task: Remove a task permanently
- set_priority: Change task priority (low, normal, high)

When asked to manage tasks, ALWAYS use the appropriate tools. After modifying tasks, use list_tasks to verify and show the user the current state."""

    # Get rate limits from CLI options
    rpm = request.config.getoption("--aitest-rpm", default=None)
    tpm = request.config.getoption("--aitest-tpm", default=None)

    def create_agent(
        deployment: str,
        system_prompt: str = default_prompt,
        max_turns: int = 5,
    ) -> Agent:
        return Agent(
            provider=Provider(model=f"azure/{deployment}", rpm=rpm, tpm=tpm),
            mcp_servers=[todo_server],
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
    return create_agent


@pytest.fixture
def keyvalue_agent_factory(test_mcp_server, request) -> Callable[..., Agent]:
    """Factory to create agents with KeyValue server.

    Use weather_agent_factory or todo_agent_factory for new tests.
    """
    # Get rate limits from CLI options
    rpm = request.config.getoption("--aitest-rpm", default=None)
    tpm = request.config.getoption("--aitest-tpm", default=None)

    def create_agent(
        deployment: str,
        system_prompt: str = "You are a helpful assistant. Use the tools to complete tasks.",
        max_turns: int = 10,
    ) -> Agent:
        return Agent(
            provider=Provider(model=f"azure/{deployment}", rpm=rpm, tpm=tpm),
            mcp_servers=[test_mcp_server],
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
    return create_agent
