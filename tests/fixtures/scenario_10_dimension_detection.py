"""Dimension detection — 2 models × 2 prompts with explicit names.

Proves auto-detection of model and system prompt dimensions.

Generates: tests/fixtures/reports/10_dimension_detection.json

Run:
    pytest tests/fixtures/scenario_10_dimension_detection.py -v \
        --aitest-json=tests/fixtures/reports/10_dimension_detection.json
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Agent, MCPServer, Provider, Wait

pytestmark = [pytest.mark.integration]

DETAILED_PROMPT = """You are a thorough banking assistant.
Use tools to manage accounts. Explain your reasoning."""

CONCISE_PROMPT = """You are a banking assistant. Be brief.
Use tools for account operations. Give short answers."""

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

TEST_MODELS = ["gpt-5-mini", "gpt-4.1-mini"]
TEST_PROMPTS = {
    "detailed": DETAILED_PROMPT,
    "concise": CONCISE_PROMPT,
}


class TestDimensionDetection:
    """2×2 matrix proving dimension auto-detection."""

    @pytest.mark.parametrize("model", TEST_MODELS, ids=TEST_MODELS)
    @pytest.mark.parametrize(
        "prompt_name,system_prompt", TEST_PROMPTS.items(), ids=TEST_PROMPTS.keys()
    )
    async def test_balance_with_all_permutations(
        self, aitest_run, model, prompt_name, system_prompt
    ):
        """Balance query across 2 models × 2 prompts = 4 runs."""
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
