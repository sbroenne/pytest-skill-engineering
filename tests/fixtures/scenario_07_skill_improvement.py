"""Skill improvement — baseline vs skilled agent.

Tests how the financial-advisor skill improves banking advice quality.

Generates: tests/fixtures/reports/07_skill_improvement.json

Run:
    pytest tests/fixtures/scenario_07_skill_improvement.py -v \
        --aitest-json=tests/fixtures/reports/07_skill_improvement.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Skill, Wait

pytestmark = [pytest.mark.integration]

BANKING_PROMPT = """You are a helpful banking assistant.
Use the available tools to manage accounts and answer questions."""

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

# Load financial advisor skill
SKILLS_DIR = Path(__file__).parent.parent / "showcase" / "skills"
FINANCIAL_SKILL = Skill.from_path(SKILLS_DIR / "financial-advisor")

AGENTS = [
    Eval.from_instructions(
        "baseline",
        BANKING_PROMPT,
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        max_turns=5,
    ),
    Eval.from_instructions(
        "with-financial-skill",
        BANKING_PROMPT,
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        skill=FINANCIAL_SKILL,
        max_turns=5,
    ),
]


@pytest.fixture(autouse=True)
def _reset_agents():
    """Reset mutable agent state after each test."""
    yield
    for a in AGENTS:
        a.max_turns = 5


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_fund_allocation_advice(eval_run, agent, llm_assert):
    """Ask for allocation advice — skilled agent should apply 50/30/20 rule."""
    agent.max_turns = 8
    result = await eval_run(agent, "How should I allocate the money across my accounts?")
    assert result.success
    assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
    assert llm_assert(result.final_response, "provides financial advice about fund allocation")


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_savings_recommendation(eval_run, agent, llm_assert):
    """Ask about savings — skilled agent should mention emergency fund."""
    agent.max_turns = 8
    result = await eval_run(agent, "I want to save more money. What do you recommend?")
    assert result.success
    assert llm_assert(result.final_response, "provides savings recommendations")
