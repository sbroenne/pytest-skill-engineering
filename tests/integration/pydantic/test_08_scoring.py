"""Level 08 — Scoring: LLM-judged rubric scoring for response quality.

Uses llm_score and ScoringDimension to evaluate prompt effectiveness
on dimensions like instruction adherence, conciseness, and actionability.
Scores flow into the report for comparison.

Permutation: LLM scoring rubric.

Run with: pytest tests/integration/pydantic/test_08_scoring.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import Eval, Provider
from pytest_skill_engineering.fixtures.llm_score import ScoringDimension, assert_score

from ..conftest import (
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration, pytest.mark.scoring]

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

    async def test_verbose_prompt_score(self, eval_run, banking_server, llm_score):
        """Score a verbose system prompt — expect lower conciseness."""
        agent = Eval.from_instructions(
            "verbose-prompt",
            VERBOSE_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await eval_run(agent, "What are all my account balances?")
        assert result.success

        score = llm_score(
            result.final_response,
            PROMPT_QUALITY_RUBRIC,
            context=result.tool_context,
        )
        assert_score(score, min_pct=0.4)

    async def test_direct_prompt_score(self, eval_run, banking_server, llm_score):
        """Score a direct system prompt — expect higher conciseness."""
        agent = Eval.from_instructions(
            "direct-prompt",
            DIRECT_PROMPT,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await eval_run(agent, "What are all my account balances?")
        assert result.success

        score = llm_score(
            result.final_response,
            PROMPT_QUALITY_RUBRIC,
            context=result.tool_context,
        )
        assert_score(score, min_pct=0.5)
