"""CLI server tests — demonstrates CLIServer usage.

Tests that agents can discover and use CLI-based tools.

Generates: tests/fixtures/reports/08_cli_server.json

Run:
    pytest tests/fixtures/scenario_08_cli_server.py -v \
        --aitest-json=tests/fixtures/reports/08_cli_server.json
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import Agent, CLIServer, Provider

pytestmark = [pytest.mark.integration]

echo_server = CLIServer(
    name="echo-cli",
    command="echo",
    tool_prefix="echo",
)

agent = Agent(
    name="cli-agent",
    provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
    cli_servers=[echo_server],
    system_prompt="You are a helpful assistant. Use echo_execute to echo messages back.",
    max_turns=5,
)


async def test_cli_echo_basic(aitest_run):
    """Basic CLI tool usage — echo a message."""
    result = await aitest_run(agent, "Echo the message 'Hello from CLI'")
    assert result.success
    assert result.tool_was_called("echo_execute")


async def test_cli_echo_with_reasoning(aitest_run, llm_assert):
    """CLI tool with reasoning — echo and explain."""
    result = await aitest_run(
        agent, "Use the echo command to say 'pytest-skill-engineering works' and confirm it worked"
    )
    assert result.success
    assert result.tool_was_called("echo_execute")
    assert llm_assert(result.final_response, "confirms the echo command executed successfully")
