"""Level 01 — Basic usage: single eval, MCP tool calls.

One eval config, no leaderboard. Proves the framework can run a prompt
against MCP tools and assert on tool usage and response content.
Includes negative test cases that verify graceful failure handling.

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


class TestBankingNegative:
    """Negative tests — verify graceful failure, correct tool assertions, and edge cases."""

    async def test_tool_not_called_assertions(self, eval_run, banking_server):
        """Verify tool_was_called() correctly returns False for uncalled tools."""
        agent = Eval.from_instructions(
            "tool-assertion-check",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=5,
        )

        result = await eval_run(agent, "What is my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")
        # These tools should NOT have been called for a simple balance inquiry
        assert not result.tool_was_called("transfer"), "Balance check should not trigger transfer"
        assert not result.tool_was_called("withdraw"), "Balance check should not trigger withdrawal"
        assert not result.tool_was_called("deposit"), "Balance check should not trigger deposit"
        assert not result.tool_was_called("nonexistent_tool"), "Nonexistent tool must return False"
        assert result.tool_call_count("nonexistent_tool") == 0

    async def test_out_of_scope_request(self, eval_run, banking_server, llm_assert):
        """Agent recognizes it cannot fulfill a request outside its tool capabilities."""
        agent = Eval.from_instructions(
            "out-of-scope",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=3,
        )

        result = await eval_run(agent, "Book me a flight to Paris for next Tuesday.")

        # Agent should complete without error, but should NOT have banking tools for flights
        assert result.success
        assert not result.tool_was_called("book_flight"), "No flight-booking tool exists"
        assert not result.tool_was_called("transfer"), "Flight request should not trigger transfer"
        assert llm_assert(
            result.final_response,
            "Explains it cannot book flights or that this is outside its capabilities. "
            "Does NOT claim to have booked a flight.",
        )

    async def test_max_turns_exhausted(self, eval_run, banking_server):
        """Agent fails when max_turns is too low to complete a complex multi-step task."""
        agent = Eval.from_instructions(
            "turns-exhausted",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=1,
        )

        result = await eval_run(
            agent,
            "Check all account balances, then transfer $100 from checking to savings, "
            "then verify the new balances and show me the transaction history.",
        )

        # With max_turns=1, the agent gets exactly one LLM request.
        # A multi-step task requiring tool calls needs multiple requests
        # (call tool → receive result → call next tool → ...).
        # The engine should hit UsageLimitExceeded → success=False.
        assert not result.success, "Complex multi-step task should not succeed with max_turns=1"
        assert result.error is not None

    async def test_nonexistent_account_graceful(self, eval_run, banking_server, llm_assert):
        """Agent handles a request for a non-existent account type gracefully."""
        agent = Eval.from_instructions(
            "bad-account",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=5,
        )

        result = await eval_run(
            agent,
            "What is the balance of my investment account?",
        )

        # The tool schema constrains account to enum ["checking", "savings"].
        # A good LLM respects the schema and tells the user no investment account exists.
        assert result.success
        assert llm_assert(
            result.final_response,
            "Indicates that an 'investment' account does not exist or is not available. "
            "May mention the available accounts (checking, savings).",
        )
