"""CLI server tests — demonstrates CLIServer usage.

Tests that agents can discover and use CLI-based tools.

Generates: tests/fixtures/reports/08_cli_server.json

Run:
    pytest tests/fixtures/scenario_08_cli_server.py -v \
        --aitest-json=tests/fixtures/reports/08_cli_server.json
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import CLIServer, Eval, Provider

pytestmark = [pytest.mark.integration]

echo_server = CLIServer(
    name="echo-cli",
    command="echo",
    tool_prefix="echo",
)

agent = Eval.from_instructions(
    "cli-agent",
    "You are a helpful assistant. Use echo_execute to echo messages back.",
    provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
    cli_servers=[echo_server],
    max_turns=5,
)


async def test_cli_echo_basic(eval_run):
    """Basic CLI tool usage — echo a message."""
    result = await eval_run(agent, "Echo the message 'Hello from CLI'")
    assert result.success
    assert result.tool_was_called("echo_execute")


async def test_cli_echo_with_reasoning(eval_run, llm_assert):
    """CLI tool with reasoning — echo and explain."""
    result = await eval_run(
        agent, "Use the echo command to say 'pytest-skill-engineering works' and confirm it worked"
    )
    assert result.success
    assert result.tool_was_called("echo_execute")
    assert llm_assert(result.final_response, "confirms the echo command executed successfully")
