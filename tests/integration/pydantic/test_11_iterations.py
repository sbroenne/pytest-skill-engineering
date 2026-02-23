"""Level 11 — Iterations: run each test N times for reliability measurement.

Uses the --aitest-iterations=N CLI flag to run each test multiple times.
The report aggregates iterations per test and shows iteration pass rate,
enabling flakiness detection and reliability baselines.

Permutation: Iteration count.

Run with: pytest tests/integration/pydantic/test_11_iterations.py -v --aitest-iterations=3
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

from ..conftest import BANKING_PROMPT, DEFAULT_MAX_TURNS, DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM

pytestmark = [pytest.mark.integration, pytest.mark.iterations]


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


class TestIterationBaseline:
    """Run banking tests multiple times to establish reliability baselines.

    When invoked with ``--aitest-iterations=3``, each test method runs
    3 times. The report aggregates iterations per test and shows an
    iteration pass rate.
    """

    async def test_balance_check_reliability(self, eval_run, banking_server):
        """Check balance — should be 100% reliable."""
        agent = Eval.from_instructions(
            "default",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await eval_run(agent, "What's my checking account balance?")
        assert result.success
        assert result.tool_was_called("get_balance")

    async def test_transfer_reliability(self, eval_run, banking_server):
        """Transfer money — may show flakiness across iterations."""
        agent = Eval.from_instructions(
            "default",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await eval_run(agent, "Transfer $100 from checking to savings.")
        assert result.success
        assert result.tool_was_called("transfer")

    async def test_multi_tool_reliability(self, eval_run, banking_server):
        """Multi-tool query — checks stability of complex operations."""
        agent = Eval.from_instructions(
            "default",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await eval_run(agent, "Show me all my account balances and recent transactions.")
        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
