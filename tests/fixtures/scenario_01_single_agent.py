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

agent = Eval.from_instructions(
    "banking-agent",
    BANKING_PROMPT,
    provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
    mcp_servers=[banking_server],
    max_turns=5,
)


@pytest.fixture(autouse=True)
def _reset_agent():
    """Reset mutable agent state after each test."""
    yield
    agent.max_turns = 5


async def test_check_balance(eval_run, llm_assert):
    """Basic balance check — should pass."""
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
    assert result.tool_call_arg("get_balance", "account") == "checking"
    assert llm_assert(result.final_response, "mentions the checking account balance amount")
    assert result.cost_usd < 0.05


async def test_transfer_between_accounts(eval_run, llm_assert):
    """Transfer money — tests the transfer tool."""
    result = await eval_run(agent, "Transfer $200 from checking to savings")
    assert result.success
    assert result.tool_was_called("transfer")
    assert result.tool_call_arg("transfer", "from_account") == "checking"
    assert result.tool_call_arg("transfer", "to_account") == "savings"
    assert result.tool_call_arg("transfer", "amount") == 200
    assert llm_assert(result.final_response, "confirms the transfer was completed")


async def test_transaction_history(eval_run, llm_assert):
    """View transactions — multiple tool calls possible."""
    agent.max_turns = 8
    result = await eval_run(agent, "Show me recent transactions for all accounts")
    assert result.success
    assert result.tool_was_called("get_transactions") or result.tool_was_called("get_all_balances")
    assert llm_assert(result.final_response, "shows transaction or balance information")


async def test_expected_failure(eval_run):
    """Test that fails due to turn limit — for report variety."""
    agent.max_turns = 1
    await eval_run(
        agent,
        "Check all balances, transfer $500 from checking to savings, then show me updated balances and transaction history",
    )
    # Intentional failure to demonstrate error display in reports
    raise AssertionError(
        "Eval exceeded turn limit - unable to process multi-step request (max_turns=1)"
    )
