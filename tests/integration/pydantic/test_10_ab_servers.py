"""Level 10 — A/B server comparison: compare different server configurations.

Useful for testing tool description improvements, different API designs,
or evaluating server refactoring. Parametrizes prompt style as the varying
dimension to show side-by-side comparison in the report.

Permutation: Server / prompt A vs B.

Run with: pytest tests/integration/pydantic/test_10_ab_servers.py -v
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

from ..conftest import (
    BANKING_PROMPT,
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration, pytest.mark.abtest]


@pytest.fixture(scope="module")
def banking_server_v1():
    """Banking server v1 — original implementation."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_skill_engineering.testing.banking_mcp",
        ],
        wait=Wait.for_tools(
            [
                "get_balance",
                "get_all_balances",
                "transfer",
                "deposit",
                "withdraw",
                "get_transactions",
            ]
        ),
    )


@pytest.fixture(scope="module")
def todo_server_v1():
    """Todo server v1 — original implementation."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_skill_engineering.testing.todo_mcp",
        ],
        wait=Wait.for_tools(["add_task", "list_tasks", "complete_task"]),
    )


# =============================================================================
# A/B Prompt Comparison
# =============================================================================


class TestServerABComparison:
    """Compare different prompt styles for the same server."""

    @pytest.mark.parametrize("server_version", ["v1-verbose", "v1-terse"])
    async def test_banking_simple_query(self, eval_run, banking_server_v1, server_version):
        """Simple balance query across different prompt styles."""
        system_prompt = (
            BANKING_PROMPT
            if server_version == "v1-verbose"
            else "You help with banking. Use tools to get data."
        )

        agent = Eval.from_instructions(
            f"banking-{server_version}",
            system_prompt,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server_v1],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.parametrize("server_version", ["v1-verbose", "v1-terse"])
    async def test_banking_transfer_query(self, eval_run, banking_server_v1, server_version):
        """Transfer operation across different prompt styles."""
        system_prompt = (
            BANKING_PROMPT
            if server_version == "v1-verbose"
            else "You help with banking. Use tools to get data."
        )

        agent = Eval.from_instructions(
            f"banking-transfer-{server_version}",
            system_prompt,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server_v1],
            max_turns=8,
        )

        result = await eval_run(
            agent,
            "Transfer $100 from checking to savings and show me the updated balances.",
        )

        assert result.success
        assert result.tool_was_called("transfer")


# =============================================================================
# Tool Description Quality Impact
# =============================================================================


class TestToolDescriptionImpact:
    """Test how tool description quality affects agent performance."""

    @pytest.mark.parametrize("description_quality", ["good", "minimal"])
    async def test_ambiguous_query_handling(self, eval_run, banking_server_v1, description_quality):
        """Test how description quality affects ambiguous query handling."""
        if description_quality == "good":
            system_prompt = (
                "You are a banking assistant. The system manages checking and savings "
                "accounts. Use get_all_balances to discover available accounts. "
                "If an operation fails, explain why and suggest alternatives."
            )
        else:
            system_prompt = "You manage bank accounts."

        agent = Eval.from_instructions(
            f"ambiguous-{description_quality}",
            system_prompt,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server_v1],
            max_turns=8,
        )

        result = await eval_run(agent, "Show me my account overview.")

        assert result.success
        tool_calls = result.tool_call_count("get_balance") + result.tool_call_count(
            "get_all_balances"
        )
        if description_quality == "good":
            assert tool_calls >= 1, "Good descriptions should enable tool usage"


# =============================================================================
# Server Migration Validation
# =============================================================================


class TestServerMigration:
    """Validate server migration/refactoring."""

    async def test_todo_workflow_consistency(self, eval_run, todo_server_v1):
        """Ensure todo workflow works consistently."""
        agent = Eval.from_instructions(
            "todo-migration-test",
            "You manage tasks. Add, complete, and list tasks as requested.",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server_v1],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Add 'buy groceries' to my shopping list, then show me all my tasks.",
        )

        assert result.success
        assert result.tool_was_called("add_task")
        assert result.tool_was_called("list_tasks")
        assert "groceries" in result.final_response.lower()
