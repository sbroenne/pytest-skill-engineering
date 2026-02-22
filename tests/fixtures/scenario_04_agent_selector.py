"""Three agents for testing the agent selector UI.

Eval selector only appears when there are 3+ agents.

Generates: tests/fixtures/reports/04_agent_selector.json

Run:
    pytest tests/fixtures/scenario_04_agent_selector.py -v \
        --aitest-json=tests/fixtures/reports/04_agent_selector.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Skill, Wait

pytestmark = [pytest.mark.integration]

BANKING_PROMPT = """You are a helpful banking assistant.
Use the available tools to manage accounts and transactions.
Always use tools - never make up balances or account data."""

banking_server = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw", "get_transactions"]
    ),
)

# Load skill for agent variation
SKILLS_DIR = Path(__file__).parent.parent / "showcase" / "skills"
FINANCIAL_SKILL = (
    Skill.from_path(SKILLS_DIR / "financial-advisor")
    if (SKILLS_DIR / "financial-advisor").exists()
    else None
)

AGENTS = [
    Eval(
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=BANKING_PROMPT,
        max_turns=5,
    ),
    Eval(
        provider=Provider(model="azure/gpt-4.1-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=BANKING_PROMPT,
        max_turns=5,
    ),
    Eval(
        provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
        mcp_servers=[banking_server],
        system_prompt=BANKING_PROMPT,
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
async def test_balance_query(eval_run, agent, llm_assert):
    """Basic balance query — all agents should pass."""
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
    assert result.tool_call_arg("get_balance", "account") == "checking"
    assert llm_assert(
        result.final_response,
        "provides the current checking account balance amount",
    )


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_financial_planning(eval_run, agent, llm_assert):
    """Financial advice — tests differentiation between agents (skill vs no skill)."""
    agent.max_turns = 8
    result = await eval_run(
        agent,
        "I have money in checking and savings. How should I allocate my funds?",
    )
    assert result.success
    assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
    assert llm_assert(result.final_response, "provides financial advice about fund allocation")
