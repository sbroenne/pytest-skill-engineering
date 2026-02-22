"""Hero test suite for README showcase.

A lean banking scenario demonstrating ALL pytest-skill-engineering capabilities
with minimal test count for fast execution:

1. Model Comparison - 3 core tests across 2 models -> agent leaderboard
2. Multi-Turn Sessions - 2-turn conversation with context continuity
3. Prompt Comparison - 1 test across 3 prompt styles
4. Skill Integration - 1 test with financial advisor skill
5. Iterations - All tests run N times when ``--aitest-iterations`` is set

Output: docs/demo/hero-report.html
Command: pytest tests/showcase/ -v --aitest-iterations=2 --aitest-html=docs/demo/hero-report.html --aitest-summary-model=azure/gpt-5.2-chat
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Skill, Wait, load_custom_agents

# Mark all tests as showcase
pytestmark = [pytest.mark.showcase]

# =============================================================================
# Constants
# =============================================================================

BENCHMARK_MODELS = ["gpt-5-mini", "gpt-4.1"]
DEFAULT_RPM = 200
DEFAULT_TPM = 200000
DEFAULT_MAX_TURNS = 8

# Banking system prompt — used for ALL core tests (same prompt = fair comparison)
BANKING_PROMPT = """You are a banking assistant with access to account management tools \
in a simulated demo environment.

IMPORTANT: Always use the available tools to manage accounts. Never guess balances \
or transaction details - the tools provide accurate, real-time data.

Available tools:
- get_balance: Get current balance for a specific account
- get_all_balances: See all account balances at once
- transfer: Move money between accounts
- deposit: Add money to an account
- withdraw: Take money from an account
- get_transactions: View transaction history

When asked about accounts, ALWAYS call the appropriate tool first, then respond \
based on the tool's output. If an operation fails, explain why and suggest alternatives."""

# =============================================================================
# Agents — defined once at module level, reused across tests.
# Same Eval object = same UUID = correct grouping in reports.
# =============================================================================

BANKING_SERVER = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
    wait=Wait.for_tools(
        [
            "get_balance",
            "get_all_balances",
            "transfer",
            "deposit",
            "withdraw",
            "get_transactions",
        ]
    ),
)

# Core agents — one per model, same prompt → fair leaderboard
CORE_AGENTS = [
    Eval.from_instructions(
        "default",
        BANKING_PROMPT,
        provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
        mcp_servers=[BANKING_SERVER],
        max_turns=DEFAULT_MAX_TURNS,
    )
    for model in BENCHMARK_MODELS
]

# Prompt agents — model × prompt combinations
PROMPTS_DIR = Path(__file__).parent / "prompts"
ADVISOR_PROMPTS_DATA = load_custom_agents(PROMPTS_DIR) if PROMPTS_DIR.exists() else []

PROMPT_AGENTS = [
    Eval.from_instructions(
        agent_data["name"],
        agent_data["prompt"],
        provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
        mcp_servers=[BANKING_SERVER],
        max_turns=DEFAULT_MAX_TURNS,
    )
    for model in BENCHMARK_MODELS
    for agent_data in ADVISOR_PROMPTS_DATA
]

# Skill agents — core agent + financial advisor skill
_SKILL_PATH = Path(__file__).parent / "skills" / "financial-advisor"
_FINANCIAL_SKILL = Skill.from_path(_SKILL_PATH) if _SKILL_PATH.exists() else None

SKILL_AGENTS = (
    [
        Eval.from_instructions(
            "default",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[BANKING_SERVER],
            skill=_FINANCIAL_SKILL,
            max_turns=DEFAULT_MAX_TURNS,
        )
        for model in BENCHMARK_MODELS
    ]
    if _FINANCIAL_SKILL
    else []
)


# =============================================================================
# 1. Core Tests — Model Leaderboard
# =============================================================================


class TestCoreOperations:
    """Core banking tests — parametrized across benchmark agents.

    Every agent runs the same tests with the same prompt, so the
    leaderboard comparison is fair.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_check_balance(self, eval_run, agent):
        """Check account balance."""
        result = await eval_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_transfer_funds(self, eval_run, agent):
        """Transfer funds between accounts."""
        result = await eval_run(
            agent,
            "Move $100 from my checking account to my savings account.",
        )

        assert result.success
        assert result.tool_was_called("transfer")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_error_handling(self, eval_run, llm_assert, agent):
        """Handle insufficient funds gracefully."""
        result = await eval_run(
            agent,
            "Transfer $50,000 from my checking to savings.",
        )

        assert result.success
        assert len(result.all_tool_calls) >= 1
        assert llm_assert(
            result.final_response,
            "explains insufficient funds or suggests an alternative",
        )


# =============================================================================
# 2. Session Continuity — Multi-turn conversation
# =============================================================================


@pytest.mark.session("savings-planning")
class TestSavingsPlanningSession:
    """Multi-turn session: savings transfer workflow.

    Tests that the agent remembers context across turns:
    - Turn 1: Check balances
    - Turn 2: Transfer based on previous context
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_01_check_balances(self, eval_run, agent):
        """First turn: check account balances."""
        result = await eval_run(agent, "Show me all my account balances.")

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_02_transfer_funds(self, eval_run, agent):
        """Second turn: transfer based on previous context."""
        result = await eval_run(
            agent,
            "Move $200 from checking to savings.",
        )

        assert result.success
        assert result.tool_was_called("transfer")


# =============================================================================
# 3. Prompt Comparison — Different system prompt styles
# =============================================================================


@pytest.mark.skipif(not PROMPT_AGENTS, reason="No prompts found")
class TestPromptComparison:
    """Compare how different prompt styles affect responses."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", PROMPT_AGENTS, ids=lambda a: a.name)
    async def test_advice_style(self, eval_run, agent):
        """Compare advisory styles across prompts."""
        result = await eval_run(
            agent,
            "Check my accounts and give me advice on managing my money better.",
        )

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")


# =============================================================================
# 4. Skill Integration — Domain knowledge enhancement
# =============================================================================


@pytest.mark.skipif(not SKILL_AGENTS, reason="Financial advisor skill not found")
class TestSkillEnhancement:
    """Test how skills improve advice quality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", SKILL_AGENTS, ids=lambda a: a.name)
    async def test_with_financial_skill(self, eval_run, llm_assert, agent):
        """Eval with financial advisor skill gives better advice."""
        result = await eval_run(
            agent,
            "I have $1500 in checking. Should I keep it there or move some to savings? "
            "What's a good emergency fund target?",
        )

        assert result.success
        assert llm_assert(
            result.final_response,
            "provides financial advice about savings or emergency funds",
        )
