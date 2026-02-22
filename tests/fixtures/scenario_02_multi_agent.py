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

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

pytestmark = [pytest.mark.integration]

BANKING_PROMPT = """You are a helpful banking assistant.
Use the available tools to manage accounts and transactions.
Always use tools - never make up balances or account data."""

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

AGENTS = [
    Eval.from_instructions(
        "default",
        BANKING_PROMPT,
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        max_turns=5,
    ),
    Eval.from_instructions(
        "default",
        BANKING_PROMPT,
        provider=Provider(model="azure/gpt-4.1-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
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
async def test_check_balance(eval_run, agent, llm_assert):
    """Basic balance query — all agents should pass."""
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
    assert result.tool_call_arg("get_balance", "account") == "checking"
    assert llm_assert(result.final_response, "states the checking account balance amount")


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_transfer_and_verify(eval_run, agent, llm_assert):
    """Transfer with verification — tests multi-step tool use."""
    agent.max_turns = 8
    result = await eval_run(
        agent, "Transfer $100 from checking to savings, then show me both balances"
    )
    assert result.success
    assert result.tool_was_called("transfer")
    assert result.tool_call_arg("transfer", "amount") == 100
    assert result.tool_call_count("get_balance") >= 1 or result.tool_was_called("get_all_balances")
    assert llm_assert(result.final_response, "confirms the transfer and shows updated balances")
    assert result.duration_ms < 30000


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_error_handling(eval_run, agent, llm_assert):
    """Insufficient funds — tests error recovery."""
    agent.max_turns = 8
    result = await eval_run(agent, "Withdraw $50,000 from my checking account")
    assert result.success
    assert result.tool_was_called("withdraw")
    assert llm_assert(
        result.final_response,
        "explains that the withdrawal failed due to insufficient funds",
    )
