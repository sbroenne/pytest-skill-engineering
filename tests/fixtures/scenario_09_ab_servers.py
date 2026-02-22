"""A/B server comparison — verbose vs terse system prompts.

Tests how system prompt verbosity affects agent performance.

Generates: tests/fixtures/reports/09_ab_servers.json

Run:
    pytest tests/fixtures/scenario_09_ab_servers.py -v \
        --aitest-json=tests/fixtures/reports/09_ab_servers.json
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

pytestmark = [pytest.mark.integration]

VERBOSE_PROMPT = """You are a banking assistant with access to account management tools.

IMPORTANT: Always use the available tools to manage accounts. Never guess balances.

Available tools:
- get_balance: Get current balance for a specific account
- get_all_balances: See all account balances at once
- transfer: Move money between accounts
- deposit: Add money to an account
- withdraw: Take money from an account
- get_transactions: View transaction history

When asked about accounts, ALWAYS call the appropriate tool first."""

TERSE_PROMPT = "You help with banking. Use tools to get data."

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

AGENTS = [
    Eval(
        name="verbose-prompt",
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=VERBOSE_PROMPT,
        max_turns=5,
    ),
    Eval(
        name="terse-prompt",
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=TERSE_PROMPT,
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
async def test_simple_balance_query(eval_run, agent):
    """Simple query — should work with both prompts."""
    result = await eval_run(agent, "What's my checking balance?")
    assert result.success
    assert result.tool_was_called("get_balance")


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_multi_step_transfer(eval_run, agent, llm_assert):
    """Multi-step operation — verbose prompt may perform better."""
    agent.max_turns = 8
    result = await eval_run(
        agent,
        "Transfer $100 from checking to savings, then show me both balances",
    )
    assert result.success
    assert result.tool_was_called("transfer")
    assert llm_assert(result.final_response, "confirms a transfer and shows balances")
