"""Level 07 — Clarification detection: catch evals that ask instead of acting.

Validates the ClarificationDetection feature which uses an LLM judge to
detect "Would you like me to...?" style responses. Clear requests should
NOT trigger clarification; the eval should act immediately.

Permutation: ClarificationDetection enabled on eval.

Run with: pytest tests/integration/pydantic/test_07_clarification.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import ClarificationDetection, ClarificationLevel, Eval, Provider

from ..conftest import (
    BANKING_PROMPT,
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration, pytest.mark.clarification]


class TestClarificationDetection:
    """Tests for clarification detection feature."""

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

    async def test_no_clarification_on_transfer(self, eval_run, banking_server):
        """Transfer with explicit amounts should not trigger clarification."""
        agent = Eval.from_instructions(
            "transfer-no-clarification",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
            clarification_detection=ClarificationDetection(
                enabled=True,
                level=ClarificationLevel.ERROR,
            ),
        )

        result = await eval_run(agent, "Transfer $100 from checking to savings.")

        assert result.success
        assert result.tool_was_called("transfer")
        assert not result.asked_for_clarification

    async def test_no_clarification_on_multi_step(self, eval_run, banking_server):
        """Multi-step request should not trigger clarification."""
        agent = Eval.from_instructions(
            "multi-step-no-clarification",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=8,
            clarification_detection=ClarificationDetection(
                enabled=True,
                level=ClarificationLevel.ERROR,
            ),
        )

        result = await eval_run(
            agent,
            "Check my checking balance, then deposit $200 into it.",
        )

        assert result.success
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")
        assert result.tool_was_called("deposit")
        assert not result.asked_for_clarification
