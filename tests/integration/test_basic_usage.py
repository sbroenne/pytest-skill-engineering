"""Basic usage tests - multi-step workflows with MCP tools.

These tests demonstrate realistic agent workflows that require multiple tool calls,
reasoning between steps, and validation of end-to-end behavior.

Run with: pytest tests/integration/test_basic_usage.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import ClarificationDetection, ClarificationLevel, Eval, Provider

from .conftest import (
    BANKING_PROMPT,
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
    TODO_PROMPT,
)

pytestmark = [pytest.mark.integration, pytest.mark.basic]


# =============================================================================
# Banking Server - Multi-step Workflows
# =============================================================================


class TestBankingWorkflows:
    """Multi-step banking workflows that test real-world usage patterns."""

    @pytest.mark.asyncio
    async def test_balance_check_and_transfer(self, eval_run, banking_server, llm_assert):
        """Check balance, transfer funds, verify — classic multi-step workflow.

        This tests:
        - Multiple sequential tool calls
        - Reasoning across retrieved data
        - Verification after mutation
        - AI judge for semantic validation
        """
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
        # Should check balance first, then transfer, then verify
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")
        assert result.tool_was_called("transfer")
        # Should synthesize an answer mentioning both accounts
        response_lower = result.final_response.lower()
        assert "checking" in response_lower
        assert "savings" in response_lower
        # AI judge validates the workflow
        assert llm_assert(
            result.final_response,
            """
            - Shows account balances
            - Confirms the transfer was completed
            - Reports updated balances
        """,
        )

    @pytest.mark.asyncio
    async def test_deposit_and_withdrawal_workflow(self, eval_run, banking_server):
        """Deposit money, then withdraw a different amount.

        This tests:
        - Sequential state-changing operations
        - Different tool usage (deposit vs withdraw)
        - Balance awareness across operations
        """
        agent = Eval.from_instructions(
            "deposit-withdraw",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Deposit $500 into my checking account, then withdraw $100 from it. "
            "What's the final balance?",
        )

        assert result.success
        assert result.tool_was_called("deposit")
        assert result.tool_was_called("withdraw")
        # Should mention the final balance
        response_lower = result.final_response.lower()
        assert any(word in response_lower for word in ["balance", "$", "1,900", "1900"])

    @pytest.mark.asyncio
    async def test_discovery_then_action_workflow(self, eval_run, banking_server):
        """Discover all accounts, then act on the largest one.

        This tests:
        - Discovery phase (list available resources)
        - Decision making based on discovered data
        - Follow-up action based on analysis
        """
        agent = Eval.from_instructions(
            "account-explorer",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Show me all my accounts. Which one has the most money? "
            "Deposit $100 into that account.",
        )

        assert result.success
        # Should discover accounts first
        assert result.tool_was_called("get_all_balances")
        # Should then deposit into savings (largest: $3,000)
        assert result.tool_was_called("deposit")
        assert "savings" in result.final_response.lower()

    @pytest.mark.asyncio
    async def test_transaction_history_analysis(self, eval_run, banking_server):
        """Make transactions then review history.

        This tests:
        - Multiple mutations followed by read
        - Data aggregation and analysis
        - Structured output from transaction log
        """
        agent = Eval.from_instructions(
            "transaction-analyst",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=12,
        )

        result = await eval_run(
            agent,
            "Transfer $50 from savings to checking, then deposit $200 into checking. "
            "Show me the checking account transaction history.",
        )

        assert result.success
        assert result.tool_was_called("transfer")
        assert result.tool_was_called("deposit")
        assert result.tool_was_called("get_transactions")
        response_lower = result.final_response.lower()
        assert "checking" in response_lower

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, eval_run, banking_server):
        """Handle insufficient funds gracefully and provide alternatives.

        This tests:
        - Error handling from tool
        - Recovery behavior
        - Graceful degradation
        """
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
        # Should try the withdrawal first
        assert result.tool_was_called("withdraw")
        # Should recover by checking balance
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")


# =============================================================================
# Todo Server - Multi-step Workflows
# =============================================================================


class TestTodoWorkflows:
    """Multi-step task management workflows that test stateful operations."""

    @pytest.mark.asyncio
    async def test_project_setup_workflow(self, eval_run, todo_server):
        """Create multiple tasks and verify the list.

        This tests:
        - Multiple sequential writes
        - State persistence between calls
        - Verification via read
        """
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
        # Should add all three items
        assert result.tool_call_count("add_task") >= 3
        # Should verify with list
        assert result.tool_was_called("list_tasks")
        # Final response should confirm all items
        response_lower = result.final_response.lower()
        assert "milk" in response_lower
        assert "bread" in response_lower
        assert "eggs" in response_lower

    @pytest.mark.asyncio
    async def test_task_lifecycle_workflow(self, eval_run, todo_server, llm_assert):
        """Full task lifecycle: create, complete, verify.

        This tests:
        - Create → state change → verify pattern
        - ID tracking between operations
        - State verification after mutations
        - AI judge for semantic validation
        """
        agent = Eval.from_instructions(
            "task-lifecycle",
            TODO_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Add 'review quarterly report' to my work list. "
            "Then mark it as complete. "
            "Finally show my work list to confirm it's marked done.",
        )

        assert result.success
        # Full lifecycle: add → complete → verify
        assert result.tool_was_called("add_task")
        assert result.tool_was_called("complete_task")
        assert result.tool_was_called("list_tasks")
        # AI judge validates the workflow report
        assert llm_assert(
            result.final_response,
            """
            - Confirms task was added
            - Indicates task was marked complete
            - Shows or describes the final list state
        """,
        )

    @pytest.mark.asyncio
    async def test_priority_management_workflow(self, eval_run, todo_server):
        """Create tasks with different priorities and query by priority.

        This tests:
        - Parameter usage (priority field)
        - Querying/filtering results
        - Understanding of priority semantics
        """
        agent = Eval.from_instructions(
            "priority-manager",
            TODO_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=12,
        )

        result = await eval_run(
            agent,
            "Create three tasks in my work list:\n"
            "1. 'Fix critical bug' with HIGH priority\n"
            "2. 'Update documentation' with LOW priority\n"
            "3. 'Review PR' with NORMAL priority\n\n"
            "Then show me all tasks and tell me which one I should do first.",
        )

        assert result.success
        # Should create all three tasks
        assert result.tool_call_count("add_task") >= 3
        # Should list tasks
        assert result.tool_was_called("list_tasks")
        # Should recommend the high priority task first
        response_lower = result.final_response.lower()
        assert "critical bug" in response_lower or "high" in response_lower
        assert any(word in response_lower for word in ["first", "priority", "urgent"])

    @pytest.mark.asyncio
    async def test_batch_completion_workflow(self, eval_run, todo_server):
        """Add tasks, complete multiple, then show remaining.

        This tests:
        - Batch operations (completing multiple)
        - State tracking across operations
        - Filtering (remaining vs completed)
        """
        agent = Eval.from_instructions(
            "batch-completer",
            TODO_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=15,
        )

        result = await eval_run(
            agent,
            "Add these tasks to my quick-tasks list: 'send email', 'make call', 'write note'. "
            "Then mark 'send email' and 'make call' as complete. "
            "Finally show me only the remaining incomplete tasks.",
        )

        assert result.success
        # Should add multiple tasks
        assert result.tool_call_count("add_task") >= 3
        # Should complete multiple
        assert result.tool_call_count("complete_task") >= 2
        # Should list remaining
        assert result.tool_was_called("list_tasks")
        # The only incomplete task should be "write note"
        response_lower = result.final_response.lower()
        assert "write note" in response_lower or "note" in response_lower

    @pytest.mark.asyncio
    async def test_multi_list_organization(self, eval_run, todo_server):
        """Organize tasks across multiple lists.

        This tests:
        - Working with multiple lists/namespaces
        - Understanding list semantics
        - Cross-list queries
        """
        agent = Eval.from_instructions(
            "multi-list-organizer",
            TODO_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=12,
        )

        result = await eval_run(
            agent,
            "Add 'buy groceries' to my personal list and 'submit report' to my work list. "
            "Then tell me what lists I have and how many tasks are in each.",
        )

        assert result.success
        # Should add tasks to different lists
        assert result.tool_call_count("add_task") >= 2
        # Should query lists
        assert result.tool_was_called("get_lists") or result.tool_was_called("list_tasks")
        # Should mention both lists in response
        response_lower = result.final_response.lower()
        assert "personal" in response_lower
        assert "work" in response_lower


# =============================================================================
# Advanced Patterns
# =============================================================================


class TestAdvancedPatterns:
    """Tests for more complex agent behaviors."""

    @pytest.mark.asyncio
    async def test_ambiguous_request_clarification(self, eval_run, banking_server):
        """Handle ambiguous requests intelligently.

        This tests:
        - Interpretation of vague requests
        - Intelligent defaults or clarification
        - Graceful handling of underspecified input
        """
        agent = Eval.from_instructions(
            "ambiguity-handler",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=8,
        )

        result = await eval_run(
            agent,
            "How much money do I have?",
        )

        assert result.success
        # Eval should check balances for the user
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
        # Should mention at least one account
        response_lower = result.final_response.lower()
        assert any(acct in response_lower for acct in ["checking", "savings"])

    @pytest.mark.asyncio
    async def test_conditional_logic_workflow(self, eval_run, todo_server):
        """Execute conditional logic based on current state.

        This tests:
        - Check-then-act pattern
        - Conditional branching based on data
        - State-aware decision making
        """
        agent = Eval.from_instructions(
            "conditional-logic",
            TODO_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Check if I have any tasks in my 'urgent' list. "
            "If not, create one called 'check email' with high priority. "
            "Show me the urgent list either way.",
        )

        assert result.success
        # Should check the list first
        assert result.tool_was_called("list_tasks") or result.tool_was_called("get_lists")
        # Should create the task (since urgent list is empty initially)
        assert result.tool_was_called("add_task")
        # Should verify
        assert result.tool_call_count("list_tasks") >= 1


# =============================================================================
# Clarification Detection
# =============================================================================


class TestClarificationDetection:
    """Tests for clarification detection feature.

    Verifies that agents act autonomously instead of asking
    the user for clarification when given clear instructions.
    """

    @pytest.mark.asyncio
    async def test_no_clarification_on_clear_request(self, eval_run, banking_server):
        """Eval should not ask for clarification on a clear request."""
        agent = Eval.from_instructions(
            "no-clarification",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
            clarification_detection=ClarificationDetection(
                enabled=True,
                level=ClarificationLevel.ERROR,
            ),
        )

        result = await eval_run(agent, "What's my checking balance?")

        assert result.success
        assert result.tool_was_called("get_balance")
        assert not result.asked_for_clarification
        assert result.clarification_count == 0
