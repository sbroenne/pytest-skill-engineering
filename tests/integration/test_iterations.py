"""Integration tests for --aitest-iterations support.

Demonstrates running the same test multiple times with iteration aggregation.
Uses the banking MCP server for realistic scenarios.

Run with: pytest tests/integration/test_iterations.py -v --aitest-iterations=3
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Agent, MCPServer, Provider, Wait

from .conftest import BANKING_PROMPT, DEFAULT_MAX_TURNS, DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM

# =============================================================================
# Server fixture
# =============================================================================


@pytest.fixture(scope="module")
def banking_server():
    """Banking MCP server for iteration tests."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_skill_engineering.testing.banking_mcp",
        ],
        wait=Wait.for_tools(["get_balance", "get_all_balances", "transfer"]),
    )


# =============================================================================
# Iteration Tests
# =============================================================================


class TestIterationBaseline:
    """Run banking tests multiple times to establish reliability baselines.

    When invoked with ``--aitest-iterations=3``, each test method runs
    3 times.  The report aggregates iterations per test and shows an
    iteration pass rate.
    """

    @pytest.mark.asyncio
    async def test_balance_check_reliability(self, aitest_run, banking_server):
        """Check balance — should be 100% reliable."""
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt=BANKING_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await aitest_run(agent, "What's my checking account balance?")
        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.asyncio
    async def test_transfer_reliability(self, aitest_run, banking_server):
        """Transfer money — may show flakiness across iterations."""
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt=BANKING_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await aitest_run(
            agent,
            "Transfer $100 from checking to savings.",
        )
        assert result.success
        assert result.tool_was_called("transfer")

    @pytest.mark.asyncio
    async def test_multi_tool_reliability(self, aitest_run, banking_server):
        """Multi-tool query — checks stability of complex operations."""
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt=BANKING_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await aitest_run(
            agent,
            "Show me all my account balances and recent transactions.",
        )
        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
