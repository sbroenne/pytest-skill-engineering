"""Level 06 — Sessions: multi-turn conversations with context retention.

Uses @pytest.mark.session to share conversation state between tests.
The "Paris trip" pattern proves context retention: the agent must remember
information from earlier turns that no tool can provide.

Permutation: Multi-turn session state.

Run with: pytest tests/integration/pydantic/test_06_sessions.py -v
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

from ..conftest import BENCHMARK_MODELS, DEFAULT_RPM, DEFAULT_TPM

pytestmark = [pytest.mark.integration, pytest.mark.session_test]

DEFAULT_MODEL = "gpt-5-mini"

BANKING_PROMPT = (
    "You are a helpful banking assistant. Help users manage their checking "
    "and savings accounts. Be concise but thorough. When users ask about "
    "balances or transactions, always use the available tools to get "
    "current information - don't guess or use stale data."
)


@pytest.fixture(scope="module")
def banking_server():
    """Module-scoped banking server — state persists across session tests."""
    return MCPServer(
        command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
        wait=Wait.for_tools(["get_balance", "transfer", "get_transactions"]),
    )


# =============================================================================
# TestBankingWorkflow: multi-turn session proving context retention
# =============================================================================


@pytest.mark.session("banking-workflow")
class TestBankingWorkflow:
    """Multi-turn banking workflow using @pytest.mark.session.

    Test Flow
    ---------
    test_01: Introduce "Paris trip" context, check balances
    test_02: Say "that trip" (not Paris), transfer money
    test_03: Ask "what was I saving for?" — ONLY answerable from context
    test_04: Complex question requiring context + tool calls
    test_05: Summary — tests full history retention
    """

    async def test_01_introduce_context(self, eval_run, llm_assert, banking_server):
        """Establish memorable context (Paris trip) and check balances."""
        agent = Eval.from_instructions(
            "banking-session-01",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Hi! I'm planning a trip to Paris next summer and want to start "
            "saving for it. Can you check my account balances first?",
        )

        assert result.success
        balance_calls = result.tool_call_count("get_balance") + result.tool_call_count(
            "get_all_balances"
        )
        assert balance_calls >= 1
        assert llm_assert(
            result.final_response,
            "Response shows account balances (checking and/or savings amounts)",
        )

    async def test_02_reference_prior_context(self, eval_run, llm_assert, banking_server):
        """Reference prior context — says 'that trip' not 'Paris'."""
        agent = Eval.from_instructions(
            "banking-session-02",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Great! Let's start saving. Move $500 from checking to savings "
            "for that trip I mentioned.",
        )

        assert result.success
        assert result.tool_was_called("transfer")
        assert llm_assert(
            result.final_response,
            "Response confirms the transfer of $500 to savings was completed",
        )

    async def test_03_pure_context_question(self, eval_run, banking_server):
        """CRITICAL: question only answerable from conversation history.

        No tool provides "Paris" — the eval MUST remember it from test_01.
        """
        agent = Eval.from_instructions(
            "banking-session-03",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(agent, "Wait, remind me - what was I saving for again?")

        assert result.success
        assert "paris" in result.final_response.lower(), (
            f"Eval must remember 'Paris' from conversation history.\nGot: {result.final_response}"
        )

    async def test_04_multi_turn_reasoning(self, eval_run, llm_assert, banking_server):
        """Complex question requiring both context retention AND tool usage."""
        agent = Eval.from_instructions(
            "banking-session-04",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "If I keep saving $500 per month for my trip, and flights to "
            "where I'm going cost about $800, how many months until I can "
            "afford the flight? Check my current savings balance first.",
        )

        assert result.success
        assert result.tool_was_called("get_balance")
        assert llm_assert(
            result.final_response,
            "Response shows current savings balance and calculates how long "
            "until they can afford an $800 flight (likely already can with ~$3,500)",
        )

    async def test_05_context_summary(self, eval_run, llm_assert, banking_server):
        """Summary — verifies full conversation history retention."""
        agent = Eval.from_instructions(
            "banking-session-05",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent, "Give me a quick summary of what we've discussed and done today."
        )

        assert result.success
        assert llm_assert(
            result.final_response,
            "Summary mentions the Paris trip goal and the $500 transfer to savings.",
        )


# =============================================================================
# Session Isolation
# =============================================================================


@pytest.mark.session("isolated-session")
class TestSessionIsolation:
    """Different session names get independent conversations."""

    async def test_fresh_session_starts_clean(self, eval_run, banking_server):
        """This class should NOT see TestBankingWorkflow's conversation."""
        agent = Eval.from_instructions(
            "isolated-session-test",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(agent, "What's my current checking balance?")

        assert result.success
        assert result.tool_was_called("get_balance")


# =============================================================================
# Model comparison: single-turn context awareness
# =============================================================================


class TestModelSessionComparison:
    """Compare how different models handle context-rich prompts.

    Rather than calling eval_run multiple times (which creates separate
    engine instances), we test each model with a single prompt that
    requires understanding embedded context.
    """

    @pytest.mark.parametrize("model", BENCHMARK_MODELS)
    async def test_session_context_retention(self, eval_run, banking_server, model):
        """Single prompt with rich context — model must reference it."""
        agent = Eval.from_instructions(
            f"model-comparison-{model}",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "I'm saving for a trip to Paris next summer. "
            "Check my savings balance and tell me if I have enough for an $800 flight.",
        )
        assert result.success
        assert result.tool_was_called("get_balance")
        assert "paris" in result.final_response.lower() or "$" in result.final_response, (
            f"{model} didn't address the Paris trip context.\nResponse: {result.final_response}"
        )
