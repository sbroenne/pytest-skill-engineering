"""Multi-turn banking session with 2 agents.

Tests session grouping and agent comparison together.

Generates: tests/fixtures/reports/03_multi_agent_sessions.json

Run:
    pytest tests/fixtures/scenario_03_sessions.py -v \
        --aitest-json=tests/fixtures/reports/03_multi_agent_sessions.json
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

pytestmark = [pytest.mark.integration]

BANKING_PROMPT = (
    "You are a helpful banking assistant. Use tools to help users manage their accounts."
)

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

AGENTS = [
    Eval(
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=BANKING_PROMPT,
        max_turns=5,
    ),
    Eval(
        provider=Provider(model="azure/gpt-4.1-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=BANKING_PROMPT,
        max_turns=5,
    ),
]


@pytest.mark.session("banking-workflow")
class TestBankingWorkflow:
    """Multi-turn banking session with 2 agents."""

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
    async def test_check_balance(self, eval_run, agent, llm_assert):
        """First turn: check account balance."""
        result = await eval_run(agent, "What's my checking account balance?")
        assert result.success
        assert result.tool_was_called("get_balance")
        assert result.tool_call_arg("get_balance", "account") == "checking"
        assert llm_assert(result.final_response, "states the checking account balance amount")

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
    async def test_transfer_funds(self, eval_run, agent, llm_assert):
        """Second turn: transfer money."""
        result = await eval_run(agent, "Transfer $100 from checking to savings")
        assert result.success
        assert result.tool_was_called("transfer")
        assert result.tool_call_arg("transfer", "from_account") == "checking"
        assert result.tool_call_arg("transfer", "to_account") == "savings"
        assert result.tool_call_arg("transfer", "amount") == 100
        assert result.is_session_continuation
        assert llm_assert(
            result.final_response,
            "confirms the transfer of $100 from checking to savings",
        )

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
    async def test_verify_transfer(self, eval_run, agent, llm_assert):
        """Third turn: verify the transfer."""
        result = await eval_run(agent, "Show me all my account balances now")
        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
        assert result.is_session_continuation
        assert llm_assert(result.final_response, "shows balances for multiple accounts")
