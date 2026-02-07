"""Hero test suite for README showcase.

A cohesive banking scenario demonstrating ALL pytest-aitest capabilities:

1. Model Comparison - Core tests run across ALL benchmark models (fair leaderboard)
2. Multi-Turn Sessions - Context continuity across conversation turns
3. Prompt Comparison - Compare advisory styles (concise vs detailed vs friendly)
4. Skill Integration - Financial advisor skill enhancement

Output: docs/demo/hero-report.html
Command: pytest tests/showcase/ -v --aitest-html=docs/demo/hero-report.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_aitest import Agent, MCPServer, Provider, Skill, Wait, load_system_prompts

# Mark all tests as showcase
pytestmark = [pytest.mark.showcase]

# =============================================================================
# Constants
# =============================================================================

BENCHMARK_MODELS = ["gpt-5-mini", "gpt-4.1"]
DEFAULT_RPM = 10
DEFAULT_TPM = 10000
DEFAULT_MAX_TURNS = 8

# Banking system prompt — used for ALL core tests (same prompt = fair comparison)
BANKING_PROMPT = (
    "You are a personal finance assistant helping users manage their bank accounts. "
    "You have access to tools for checking balances, making transfers, deposits, "
    "withdrawals, and viewing transaction history. "
    "Always use your tools to look up real data before answering. "
    "If an operation fails, explain why and suggest alternatives. "
    "If a request is ambiguous, ask for clarification."
)

# =============================================================================
# Agents — defined once at module level, reused across tests.
# Same Agent object = same UUID = correct grouping in reports.
# =============================================================================

BANKING_SERVER = MCPServer(
    command=[sys.executable, "-u", "-m", "pytest_aitest.testing.banking_mcp"],
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
    Agent(
        name=model,
        provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
        mcp_servers=[BANKING_SERVER],
        system_prompt=BANKING_PROMPT,
        max_turns=DEFAULT_MAX_TURNS,
    )
    for model in BENCHMARK_MODELS
]

# Prompt agents — model × prompt combinations
PROMPTS_DIR = Path(__file__).parent / "prompts"
ADVISOR_PROMPTS = load_system_prompts(PROMPTS_DIR) if PROMPTS_DIR.exists() else {}

PROMPT_AGENTS = [
    Agent(
        name=f"{model}+{prompt_name}",
        provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
        mcp_servers=[BANKING_SERVER],
        system_prompt=system_prompt,
        system_prompt_name=prompt_name,
        max_turns=DEFAULT_MAX_TURNS,
    )
    for model in BENCHMARK_MODELS
    for prompt_name, system_prompt in ADVISOR_PROMPTS.items()
]

# Skill agents — core agent + financial advisor skill
_SKILL_PATH = Path(__file__).parent / "skills" / "financial-advisor"
_FINANCIAL_SKILL = Skill.from_path(_SKILL_PATH) if _SKILL_PATH.exists() else None

SKILL_AGENTS = (
    [
        Agent(
            name=f"{model}+financial-advisor",
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[BANKING_SERVER],
            system_prompt=BANKING_PROMPT,
            skill=_FINANCIAL_SKILL,
            max_turns=DEFAULT_MAX_TURNS,
        )
        for model in BENCHMARK_MODELS
    ]
    if _FINANCIAL_SKILL
    else []
)


# =============================================================================
# 1. Core Tests - ALL models run ALL of these (fair leaderboard)
# =============================================================================


class TestCoreOperations:
    """Core banking tests — parametrized across all benchmark agents.

    Every agent runs the same tests with the same prompt, so the
    leaderboard comparison is fair.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_check_single_balance(self, aitest_run, agent):
        """Check balance of one account."""
        result = await aitest_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_view_all_balances(self, aitest_run, agent):
        """View all account balances."""
        result = await aitest_run(agent, "Show me all my account balances.")

        assert result.success
        assert result.tool_was_called("get_all_balances")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_transfer_and_verify(self, aitest_run, llm_assert, agent):
        """Transfer money and verify the result with balance check."""
        result = await aitest_run(
            agent,
            "Transfer $100 from checking to savings, then show me my new balances.",
        )

        assert result.success
        assert result.tool_was_called("transfer")
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
        assert llm_assert(result.final_response, "shows updated balances after transfer")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_transaction_analysis(self, aitest_run, llm_assert, agent):
        """Get transaction history and summarize spending."""
        result = await aitest_run(
            agent,
            "Show me my recent transactions and summarize my spending patterns.",
        )

        assert result.success
        assert result.tool_was_called("get_transactions")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_financial_advice(self, aitest_run, llm_assert, agent):
        """Provide financial advice based on account data."""
        result = await aitest_run(
            agent,
            "I have some money in checking. Should I move some to savings? "
            "Check my balances and give me a recommendation.",
        )

        assert result.success
        assert len(result.all_tool_calls) >= 1
        assert llm_assert(
            result.final_response,
            "provides recommendation based on account balances",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_insufficient_funds(self, aitest_run, llm_assert, agent):
        """Handle insufficient funds gracefully."""
        result = await aitest_run(
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
# 2. Session Continuity - Multi-turn conversation
# =============================================================================


@pytest.mark.session("savings-planning")
class TestSavingsPlanningSession:
    """Multi-turn session: Planning savings transfers.

    Tests that the agent remembers context across turns:
    - Turn 1: Check balances and discuss savings
    - Turn 2: Reference "my savings" (must remember context)
    - Turn 3: Follow up on the plan
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_01_establish_context(self, aitest_run, llm_assert, agent):
        """First turn: check balances and discuss savings goals."""
        result = await aitest_run(
            agent,
            "I want to save more money. Can you check my accounts and suggest "
            "how much I could transfer to savings each month?",
        )

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
        assert llm_assert(result.final_response, "provides savings suggestion based on balances")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_02_reference_previous(self, aitest_run, llm_assert, agent):
        """Second turn: reference previous context."""
        result = await aitest_run(
            agent,
            "That sounds good. Let's start by moving $200 to savings right now.",
        )

        assert result.success
        assert result.tool_was_called("transfer")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", CORE_AGENTS, ids=lambda a: a.name)
    async def test_03_verify_result(self, aitest_run, llm_assert, agent):
        """Third turn: verify the transfer worked."""
        result = await aitest_run(
            agent,
            "Great! Can you show me my new savings balance?",
        )

        assert result.success
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")


# =============================================================================
# 3. Prompt Comparison - Same model, different system prompts
# =============================================================================


@pytest.mark.skipif(not PROMPT_AGENTS, reason="No prompts found")
class TestPromptComparison:
    """Compare how different prompt styles affect responses.

    All models run all prompts — full matrix.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", PROMPT_AGENTS, ids=lambda a: a.name)
    async def test_advice_style_comparison(self, aitest_run, llm_assert, agent):
        """Compare concise vs detailed vs friendly advisory styles."""
        result = await aitest_run(
            agent,
            "I'm worried about my spending. Can you check my accounts "
            "and give me advice on managing my money better?",
        )

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")


# =============================================================================
# 4. Skill Integration - Test with domain knowledge
# =============================================================================


@pytest.mark.skipif(not SKILL_AGENTS, reason="Financial advisor skill not found")
class TestSkillEnhancement:
    """Test how skills improve advice quality."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent", SKILL_AGENTS, ids=lambda a: a.name)
    async def test_with_financial_skill(self, aitest_run, llm_assert, agent):
        """Agent with financial advisor skill should give better advice."""
        result = await aitest_run(
            agent,
            "I have $1500 in checking. Should I keep it there or move some to savings? "
            "What's a good emergency fund target?",
        )

        assert result.success
        assert llm_assert(
            result.final_response,
            "provides financial advice about savings or emergency funds",
        )
