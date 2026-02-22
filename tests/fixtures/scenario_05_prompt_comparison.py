"""Prompt comparison — same model, different system prompts.

Tests how system prompt style affects agent behavior and quality.

Generates: tests/fixtures/reports/05_prompt_comparison.json

Run:
    pytest tests/fixtures/scenario_05_prompt_comparison.py -v \
        --aitest-json=tests/fixtures/reports/05_prompt_comparison.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait, load_system_prompts

pytestmark = [pytest.mark.integration]

# Load prompts from .md files
PROMPTS_DIR = Path(__file__).parent.parent / "integration" / "prompts"
PROMPTS = load_system_prompts(PROMPTS_DIR)

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

# Create one agent per prompt style
AGENTS = [
    Eval(
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=prompt_text,
        system_prompt_name=prompt_name,
        max_turns=5,
    )
    for prompt_name, prompt_text in PROMPTS.items()
]


@pytest.fixture(autouse=True)
def _reset_agents():
    """Reset mutable agent state after each test."""
    yield
    for a in AGENTS:
        a.max_turns = 5


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_check(eval_run, agent, llm_assert):
    """Balance query — tests how prompt style affects response format."""
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
    assert llm_assert(result.final_response, "states the checking account balance")


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_transfer_with_explanation(eval_run, agent, llm_assert):
    """Transfer with explanation — tests prompt impact on response quality."""
    agent.max_turns = 8
    result = await eval_run(
        agent, "Transfer $300 from checking to savings and explain what happened"
    )
    assert result.success
    assert result.tool_was_called("transfer")
    assert llm_assert(result.final_response, "confirms the transfer was completed")
