"""Level 01 — Basic usage: single eval, MCP tool calls.

One eval config, no leaderboard. Proves the framework can run a prompt
against MCP tools and assert on tool usage and response content.

Permutation: Nothing varies — baseline.

Run with: pytest tests/integration/pydantic/test_01_basic.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import Eval, Provider

from ..conftest import (
    BANKING_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
    TODO_PROMPT,
)

pytestmark = [pytest.mark.integration, pytest.mark.basic]


class TestBankingBasic:
    """Basic banking tool usage — single eval, no comparison."""

    async def test_balance_check_and_transfer(self, eval_run, banking_server, llm_assert):
        """Check balance, transfer funds, verify — classic multi-step workflow."""
        agent = Eval.from_instructions(
            "balance-transfer",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Check my checking account balance, then transfer $200 to savings. "
            "Show me both balances after the transfer.",
        )

        assert result.success
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")
        assert result.tool_was_called("transfer")
        response_lower = result.final_response.lower()
        assert "checking" in response_lower
        assert "savings" in response_lower
        assert llm_assert(
            result.final_response,
            "Shows account balances. Confirms the transfer was completed. Reports updated balances.",
        )

    async def test_error_recovery(self, eval_run, banking_server):
        """Handle insufficient funds gracefully and recover."""
        agent = Eval.from_instructions(
            "error-handler",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=8,
        )

        result = await eval_run(
            agent,
            "Withdraw $50,000 from my checking account. If that fails, "
            "show me my actual balance so I know how much I can withdraw.",
        )

        assert result.success
        assert result.tool_was_called("withdraw")
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")


class TestTodoBasic:
    """Basic todo tool usage — single eval, no comparison."""

    async def test_add_and_list_tasks(self, eval_run, todo_server, llm_assert):
        """Create multiple tasks and verify the list."""
        agent = Eval.from_instructions(
            "project-setup",
            TODO_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=12,
        )

        result = await eval_run(
            agent,
            "Set up my groceries list: add milk, bread, and eggs. "
            "Then show me the complete list to confirm everything was added.",
        )

        assert result.success
        assert result.tool_call_count("add_task") >= 3
        assert result.tool_was_called("list_tasks")
        response_lower = result.final_response.lower()
        assert "milk" in response_lower
        assert "bread" in response_lower
        assert "eggs" in response_lower
        assert llm_assert(
            result.final_response,
            "Confirms all three grocery items were added to the list.",
        )
