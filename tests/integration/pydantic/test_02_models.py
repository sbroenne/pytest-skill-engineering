"""Level 02 — Model comparison: same test across multiple models.

Two models run the same banking query. The report shows a model leaderboard
with winner selection based on pass rate and cost.

Permutation: Model varies.

Run with: pytest tests/integration/pydantic/test_02_models.py -v
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

pytestmark = [pytest.mark.integration, pytest.mark.model]


class TestModelComparison:
    """Same banking tasks across models — report shows model leaderboard."""

    @pytest.mark.parametrize("model", BENCHMARK_MODELS, ids=BENCHMARK_MODELS)
    async def test_balance_check(self, eval_run, banking_server, model: str):
        """Simple balance query — compare cost and speed across models."""
        agent = Eval.from_instructions(
            "model-balance",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.parametrize("model", BENCHMARK_MODELS, ids=BENCHMARK_MODELS)
    async def test_transfer_workflow(self, eval_run, banking_server, model: str):
        """Multi-step transfer — compare reasoning quality across models."""
        agent = Eval.from_instructions(
            "model-transfer",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Transfer $100 from checking to savings and show me the updated balances.",
        )

        assert result.success
        assert result.tool_was_called("transfer")
