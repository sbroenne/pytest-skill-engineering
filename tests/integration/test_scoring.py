"""Integration tests for llm_score fixture with report rendering.

Validates that LLM scoring runs end-to-end with real LLM calls and
that score data flows correctly into reports.  Uses a prompt-quality
rubric — scoring adds value when evaluating system prompt effectiveness,
not MCP server mechanics (which binary assertions already cover).
"""

from __future__ import annotations

from pytest_aitest import Agent, Provider
from pytest_aitest.fixtures.llm_score import ScoringDimension, assert_score

from .conftest import (
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

# Rubric for evaluating whether a system prompt produces well-behaved responses.
# This is a user-defined rubric — the framework ships no built-in rubric.
PROMPT_QUALITY_RUBRIC: list[ScoringDimension] = [
    ScoringDimension(
        name="instruction_adherence",
        description=(
            "Does the response follow the system prompt instructions? "
            "5 = perfectly follows all instructions, 1 = ignores them."
        ),
    ),
    ScoringDimension(
        name="conciseness",
        description=(
            "Is the response appropriately concise without unnecessary filler? "
            "5 = tight and direct, 1 = verbose padding or preamble."
        ),
    ),
    ScoringDimension(
        name="actionability",
        description=(
            "Does the agent act on the request vs asking clarifying questions? "
            "5 = acts immediately using tools, 1 = asks permission or hedges."
        ),
    ),
]

VERBOSE_PROMPT = """You are a banking assistant. IMPORTANT: Always provide a thorough,
comprehensive explanation of every action you take. Describe your reasoning step by step.
Consider multiple perspectives before answering. Be detailed and complete."""

DIRECT_PROMPT = """You are a banking assistant. Use tools to answer. Be brief."""


class TestPromptScoring:
    """Compare system prompt quality via LLM scoring."""

    async def test_verbose_prompt_score(self, aitest_run, banking_server, llm_score):
        """Score a verbose system prompt — expect lower conciseness."""
        agent = Agent(
            name="verbose-prompt",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt=VERBOSE_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await aitest_run(agent, "What are all my account balances?")
        assert result.success

        score = llm_score(
            result.final_response,
            PROMPT_QUALITY_RUBRIC,
            context=result.tool_context,
        )
        assert_score(score, min_pct=0.4)

    async def test_direct_prompt_score(self, aitest_run, banking_server, llm_score):
        """Score a direct system prompt — expect higher conciseness."""
        agent = Agent(
            name="direct-prompt",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt=DIRECT_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await aitest_run(agent, "What are all my account balances?")
        assert result.success

        score = llm_score(
            result.final_response,
            PROMPT_QUALITY_RUBRIC,
            context=result.tool_context,
        )
        assert_score(score, min_pct=0.5)
