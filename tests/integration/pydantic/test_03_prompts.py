"""Level 03 — System prompt comparison: same test across different prompts.

Two system prompts (detailed vs concise) run the same banking query.
The report detects the system prompt dimension and shows prompt comparison.

Permutation: System prompt varies.

Run with: pytest tests/integration/pydantic/test_03_prompts.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import Eval, Provider

from ..conftest import (
    BANKING_PROMPT,
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration, pytest.mark.sysprompt]

CONCISE_BANKING_PROMPT = """You are a banking assistant. Be extremely brief.

Use the banking tools to answer questions. Give short, direct answers."""

TEST_PROMPTS = {
    "detailed": BANKING_PROMPT,
    "concise": CONCISE_BANKING_PROMPT,
}


class TestPromptComparison:
    """Same banking task with different system prompts — report shows prompt leaderboard."""

    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_balance_check(
        self,
        eval_run,
        banking_server,
        prompt_name: str,
        system_prompt: str,
    ):
        """Balance query with different prompt styles — compare verbosity and cost."""
        agent = Eval.from_instructions(
            prompt_name,
            system_prompt,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_account_overview(
        self,
        eval_run,
        banking_server,
        prompt_name: str,
        system_prompt: str,
    ):
        """Account overview with different prompt styles — compare completeness."""
        agent = Eval.from_instructions(
            prompt_name,
            system_prompt,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "Show me all my accounts.")

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
