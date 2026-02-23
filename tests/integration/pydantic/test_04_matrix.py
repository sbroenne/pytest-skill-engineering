"""Level 04 — Model × Prompt matrix: 2×2 grid of model and prompt combinations.

Double parametrize produces 4 runs. The report detects both model and
system prompt dimensions and shows a matrix leaderboard.

Permutation: Model varies × System prompt varies.

Run with: pytest tests/integration/pydantic/test_04_matrix.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import Eval, Provider

from ..conftest import (
    BANKING_PROMPT,
    BENCHMARK_MODELS,
    DEFAULT_MAX_TURNS,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration, pytest.mark.matrix]

CONCISE_BANKING_PROMPT = """You are a banking assistant. Be extremely brief.

Use the banking tools to answer questions. Give short, direct answers."""

TEST_PROMPTS = {
    "detailed": BANKING_PROMPT,
    "concise": CONCISE_BANKING_PROMPT,
}


class TestModelPromptMatrix:
    """2×2 matrix: model × system prompt — report shows full grid leaderboard."""

    @pytest.mark.parametrize("model", BENCHMARK_MODELS, ids=BENCHMARK_MODELS)
    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_balance_check(
        self,
        eval_run,
        banking_server,
        model: str,
        prompt_name: str,
        system_prompt: str,
    ):
        """Balance query across all model × prompt combinations."""
        agent = Eval.from_instructions(
            prompt_name,
            system_prompt,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.parametrize("model", BENCHMARK_MODELS, ids=BENCHMARK_MODELS)
    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_transfer_workflow(
        self,
        eval_run,
        banking_server,
        model: str,
        prompt_name: str,
        system_prompt: str,
    ):
        """Transfer workflow across all model × prompt combinations."""
        agent = Eval.from_instructions(
            prompt_name,
            system_prompt,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(
            agent,
            "Transfer $100 from checking to savings and confirm.",
        )

        assert result.success
        assert result.tool_was_called("transfer")
