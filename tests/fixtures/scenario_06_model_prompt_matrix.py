"""Model × Prompt matrix — Cartesian product of 2 models × 2 prompts.

Demonstrates dimension detection and matrix comparison in reports.

Generates: tests/fixtures/reports/06_model_prompt_matrix.json

Run:
    pytest tests/fixtures/scenario_06_model_prompt_matrix.py -v \
        --aitest-json=tests/fixtures/reports/06_model_prompt_matrix.json
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Agent, MCPServer, Provider, Wait

pytestmark = [pytest.mark.integration]

BANKING_PROMPT_DETAILED = """You are a thorough banking assistant.
Use tools to manage accounts. Always verify operations by checking balances."""

BANKING_PROMPT_CONCISE = """You are a banking assistant. Be brief.
Use tools for account operations. Give short answers."""

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

TEST_MODELS = ["gpt-5-mini", "gpt-4.1-mini"]
TEST_PROMPTS = {
    "detailed": BANKING_PROMPT_DETAILED,
    "concise": BANKING_PROMPT_CONCISE,
}


class TestModelPromptMatrix:
    """2×2 matrix: 2 models × 2 prompts = 4 agent configurations."""

    @pytest.mark.parametrize("model", TEST_MODELS, ids=TEST_MODELS)
    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_balance_check(self, aitest_run, model, prompt_name, system_prompt, llm_assert):
        """Balance query across all model × prompt permutations."""
        agent = Agent(
            provider=Provider(model=f"azure/{model}", rpm=10, tpm=10000),
            mcp_servers=[banking_server],
            system_prompt=system_prompt,
            system_prompt_name=prompt_name,
            max_turns=5,
        )
        result = await aitest_run(agent, "What's my checking account balance?")
        assert result.success
        assert result.tool_was_called("get_balance")
        assert llm_assert(result.final_response, "states the checking balance amount")

    @pytest.mark.parametrize("model", TEST_MODELS, ids=TEST_MODELS)
    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_transfer_workflow(
        self, aitest_run, model, prompt_name, system_prompt, llm_assert
    ):
        """Transfer workflow across all permutations."""
        agent = Agent(
            provider=Provider(model=f"azure/{model}", rpm=10, tpm=10000),
            mcp_servers=[banking_server],
            system_prompt=system_prompt,
            system_prompt_name=prompt_name,
            max_turns=8,
        )
        result = await aitest_run(agent, "Transfer $100 from checking to savings")
        assert result.success
        assert result.tool_was_called("transfer")
        assert llm_assert(result.final_response, "confirms the transfer")
