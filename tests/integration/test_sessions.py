"""Session-based testing with multi-turn conversation continuity.

This module demonstrates how to test agents across multiple conversation turns
where context must be retained between tests using the @pytest.mark.session decorator.

Key Concepts Demonstrated
-------------------------
1. **Session Decorator**: Using `@pytest.mark.session("session-name")` for state sharing
2. **Automatic Context**: The decorator handles message passing between tests
3. **Context Verification**: Testing that the agent remembers information
4. **Session Isolation**: Different session names get independent conversations
5. **Model Comparison**: Parametrizing models to compare session behavior

The "Paris Trip" Pattern
------------------------
This test proves session support by:
1. User mentions "Paris trip" in test_01
2. User says "that trip" (not Paris) in test_02 - agent must remember
3. User asks "what was I saving for?" in test_03 - ONLY answerable from context

If sessions don't work, test_03 will fail because no tool provides "Paris".

Usage
-----
    pytest tests/integration/test_sessions.py -v --aitest-summary

See Also
--------
    docs/sessions.md : Full documentation on session-based testing
    docs/test-harnesses.md : Documentation on the BankingService test harness
"""

from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

from .conftest import BENCHMARK_MODELS, DEFAULT_RPM, DEFAULT_TPM

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration]

# Default model for session tests
DEFAULT_MODEL = "gpt-5-mini"

# Banking system prompt
BANKING_PROMPT = (
    "You are a helpful banking assistant. Help users manage their checking "
    "and savings accounts. Be concise but thorough. When users ask about "
    "balances or transactions, always use the available tools to get "
    "current information - don't guess or use stale data."
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def banking_server():
    """MCP server wrapping the BankingService test harness.

    Scope: module
        The SAME server instance is used for ALL tests in this file.
        This means account balances persist and change across tests.

    The BankingService provides tools:
        - get_balance: Check one account
        - get_all_balances: Check all accounts
        - transfer: Move money between accounts
        - get_transactions: View transaction history

    Initial State:
        - Checking: $1,500.00
        - Savings: $3,000.00
    """
    return MCPServer(
        command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
        wait=Wait.for_tools(["get_balance", "transfer", "get_transactions"]),
    )


# =============================================================================
# TestBankingWorkflow: Multi-turn session proving context retention
# =============================================================================


@pytest.mark.session("banking-workflow")
class TestBankingWorkflow:
    """Multi-turn banking workflow demonstrating session continuity.

    Uses @pytest.mark.session("banking-workflow") to automatically share
    conversation state between tests. No manual message passing needed!

    Test Flow
    ---------
    test_01: User introduces "Paris trip" context, checks balances
    test_02: User says "that trip" (not Paris) and transfers money
    test_03: User asks "what was I saving for?" - ONLY answerable from context
    test_04: User asks about trip costs - requires context AND tool calls
    test_05: User asks for conversation summary - tests full history retention

    Key Insight
    -----------
    test_03 is the critical test. The question "what was I saving for?" cannot
    be answered by any tool - the agent MUST remember "Paris" from test_01.
    If sessions don't work, test_03 will fail.
    """

    @pytest.mark.asyncio
    async def test_01_introduce_context(self, eval_run, llm_assert, banking_server):
        """Establish memorable context (Paris trip) and check balances.

        This test introduces "Paris" as a memorable detail that will be
        verified in later tests. The agent should check account balances
        and acknowledge the trip planning context.
        """
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

        assert result.success, f"Eval failed: {result.error}"

        # Verify the agent used tools to get real balance data
        balance_calls = result.tool_call_count("get_balance") + result.tool_call_count(
            "get_all_balances"
        )
        assert balance_calls >= 1, "Eval should use tools to check balances"

        # Verify response quality - agent should show actual balances
        assert llm_assert(
            result.final_response,
            "Response shows account balances (checking and/or savings amounts)",
        )

    @pytest.mark.asyncio
    async def test_02_reference_prior_context(self, eval_run, llm_assert, banking_server):
        """Reference prior context without repeating it.

        Key Test Design:
            The prompt says "that trip I mentioned" NOT "Paris trip".
            The agent must remember that "that trip" refers to Paris.

        This tests implicit context retention - the agent should understand
        the reference without us restating it explicitly.
        """
        agent = Eval.from_instructions(
            "banking-session-02",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            # IMPORTANT: We say "that trip" NOT "Paris trip"
            # The agent must remember what trip we're talking about
            "Great! Let's start saving. Move $500 from checking to savings "
            "for that trip I mentioned.",
        )

        assert result.success, f"Eval failed: {result.error}"
        assert result.tool_was_called("transfer"), "Eval should make a transfer"

        # Verify the transfer was completed
        assert llm_assert(
            result.final_response,
            "Response confirms the transfer of $500 to savings was completed",
        )

    @pytest.mark.asyncio
    async def test_03_pure_context_question(self, eval_run, banking_server):
        """Ask a question that can ONLY be answered from conversation history.

        THIS IS THE CRITICAL TEST.

        The question "what was I saving for?" cannot be answered by any tool.
        The BankingService has no concept of goals or purposes - it only knows
        about accounts and transactions.

        The agent MUST retrieve "Paris" from the conversation history established
        in test_01. If sessions don't work, this test fails.
        """
        agent = Eval.from_instructions(
            "banking-session-03",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            # This cannot be answered by tools - requires memory
            "Wait, remind me - what was I saving for again?",
        )

        assert result.success, f"Eval failed: {result.error}"

        # THE DEFINITIVE ASSERTION: Eval must say "Paris"
        response_lower = result.final_response.lower()
        assert "paris" in response_lower, (
            f"Eval must remember 'Paris' from conversation history.\n"
            f"This proves sessions work - no tool provides this information.\n"
            f"Got: {result.final_response}"
        )

    @pytest.mark.asyncio
    async def test_04_multi_turn_reasoning(self, eval_run, llm_assert, banking_server):
        """Complex question requiring both context retention AND tool usage.

        This test combines:
            1. Context: "where I'm going" refers to Paris (from history)
            2. Tool call: Check current savings balance
            3. Reasoning: Calculate months to afford $800 flight
        """
        agent = Eval.from_instructions(
            "banking-session-04",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            # Requires: context (Paris), tool call (balance), math (calculation)
            "If I keep saving $500 per month for my trip, and flights to "
            "where I'm going cost about $800, how many months until I can "
            "afford the flight? Check my current savings balance first.",
        )

        assert result.success, f"Eval failed: {result.error}"

        # Eval should check the balance using tools
        assert result.tool_was_called("get_balance"), "Eval should check savings balance"

        # Eval should provide a reasonable answer with calculation
        assert llm_assert(
            result.final_response,
            "Response shows current savings balance and calculates how long "
            "until they can afford an $800 flight (likely already can with ~$3,500)",
        )

    @pytest.mark.asyncio
    async def test_05_context_summary(self, eval_run, llm_assert, banking_server):
        """Request a summary to verify full conversation history retention.

        This tests that the agent remembers the ENTIRE conversation:
            - The original Paris trip goal
            - The $500 transfer
            - The flight cost calculation
        """
        agent = Eval.from_instructions(
            "banking-session-05",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "Give me a quick summary of what we've discussed and done today.",
        )

        assert result.success, f"Eval failed: {result.error}"

        # Summary should mention key points from the entire conversation
        assert llm_assert(
            result.final_response,
            "Summary mentions the Paris trip goal and the $500 transfer "
            "to savings. This proves the agent retained conversation history.",
        )


# =============================================================================
# TestSessionIsolation: Verify sessions don't leak between test classes
# =============================================================================


@pytest.mark.session("isolated-session")
class TestSessionIsolation:
    """Verify that different session names get isolated conversations.

    This test class runs AFTER TestBankingWorkflow but uses a different
    session name, so it starts with a fresh conversation.

    Key Distinction:
        - Session (conversation): Isolated by session name
        - Server state (balances): Shared across all tests
    """

    @pytest.mark.asyncio
    async def test_fresh_session_starts_clean(self, eval_run, banking_server):
        """This class should NOT see TestBankingWorkflow's conversation.

        The conversation history should be empty because we're using a
        different session name, even though the server state (account
        balances) reflects changes from the prior test class.
        """
        agent = Eval.from_instructions(
            "isolated-session-test",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(
            agent,
            "What's my current checking balance?",
        )

        assert result.success
        assert result.tool_was_called("get_balance")

        # The balance will be ~$1,000 (reflecting prior class's transfer)
        # but this class has no knowledge of WHY the transfer happened
        # because conversation history is isolated


# =============================================================================
# TestModelComparison: Compare session handling across models
# =============================================================================


class TestModelSessionComparison:
    """Compare how different models handle session context retention.

    This tests the same multi-turn workflow across multiple models to see
    if there are differences in context retention quality.

    Note: This class uses manual message passing to test each model
    independently within a single test (parametrized comparison).
    """

    @pytest.mark.parametrize("model", BENCHMARK_MODELS)
    @pytest.mark.asyncio
    async def test_session_context_retention(self, eval_run, banking_server, model):
        """Full session workflow: introduce context → reference it → verify memory.

        This runs a complete session in a single test to compare models fairly.
        Each model gets the same prompts and must demonstrate context retention.
        """
        agent = Eval.from_instructions(
            f"model-comparison-{model}",
            BANKING_PROMPT,
            provider=Provider(model=f"azure/{model}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=10,
        )
        messages: list = []

        # Step 1: Introduce Paris trip context
        result1 = await eval_run(
            agent,
            "Hi! I'm planning a trip to Paris next summer. Can you check my savings balance?",
        )
        assert result1.success, f"{model} failed step 1: {result1.error}"
        assert result1.tool_was_called("get_balance"), f"{model} didn't check balance"
        messages = result1.messages

        # Step 2: Reference prior context without repeating it
        result2 = await eval_run(
            agent,
            "Great! Move $200 to savings for that trip I mentioned.",
            messages=messages,
        )
        assert result2.success, f"{model} failed step 2: {result2.error}"
        assert result2.tool_was_called("transfer"), f"{model} didn't transfer"
        messages = result2.messages

        # Step 3: Pure context question - THE CRITICAL TEST
        result3 = await eval_run(
            agent,
            "Remind me - what was I saving for?",
            messages=messages,
        )
        assert result3.success, f"{model} failed step 3: {result3.error}"

        # Model MUST remember "Paris" from step 1
        response_lower = result3.final_response.lower()
        assert "paris" in response_lower, (
            f"{model} failed to remember 'Paris' from conversation.\n"
            f"Response: {result3.final_response}"
        )
