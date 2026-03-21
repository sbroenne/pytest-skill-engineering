"""Level 08 — Scoring: LLM-judged rubric scoring for Copilot responses.

Uses llm_score and ScoringDimension to evaluate instruction effectiveness
on dimensions like instruction adherence, code quality, and actionability.
Scores flow into the report for comparison across instruction styles.

Mirrors pydantic/test_08_scoring.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_08_scoring.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.fixtures.llm_score import ScoringDimension, assert_score

pytestmark = [pytest.mark.copilot]

PROMPT_QUALITY_RUBRIC: list[ScoringDimension] = [
    ScoringDimension(
        name="instruction_adherence",
        description=(
            "Does the response follow the system prompt instructions? "
            "5 = perfectly follows all instructions, 1 = ignores them."
        ),
    ),
    ScoringDimension(
        name="code_quality",
        description=(
            "Is the generated code clean, typed, and documented? "
            "5 = excellent production quality, 1 = sloppy or incomplete."
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


class TestPromptScoring:
    """Compare instruction quality via LLM-judged rubric scoring."""

    async def test_verbose_instructions_score(self, copilot_eval, tmp_path, llm_score):
        """Score verbose instructions — expect high adherence, lower conciseness."""
        agent = CopilotEval(
            name="verbose-scorer",
            instructions=(
                "You are a meticulous Python developer. IMPORTANT: Explain every "
                "step in detail before and after coding. Add comprehensive docstrings "
                "to every function. Include type hints on all parameters and return "
                "values. Add inline comments explaining complex logic."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a calculator.py module with add, subtract, multiply, and divide "
            "functions. The divide function should raise ValueError on division by zero.",
        )
        assert result.success, f"Verbose run failed: {result.error}"

        score = llm_score(result.final_response, PROMPT_QUALITY_RUBRIC)
        assert_score(score, min_pct=0.4)

    async def test_direct_instructions_score(self, copilot_eval, tmp_path, llm_score):
        """Score direct instructions — expect higher actionability."""
        agent = CopilotEval(
            name="direct-scorer",
            instructions=(
                "Create Python files as requested. Be brief. No explanations. "
                "Just write the code and confirm the file was created."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a calculator.py module with add, subtract, multiply, and divide "
            "functions. The divide function should raise ValueError on division by zero.",
        )
        assert result.success, f"Direct run failed: {result.error}"

        score = llm_score(result.final_response, PROMPT_QUALITY_RUBRIC)
        assert_score(score, min_pct=0.4)

    async def test_production_instructions_score(self, copilot_eval, tmp_path, llm_score):
        """Score production-quality instructions — expect high code quality."""
        agent = CopilotEval(
            name="production-scorer",
            instructions=(
                "You are a senior Python engineer writing production code. "
                "Every function MUST have: type hints, a Google-style docstring, "
                "and proper error handling. Use descriptive variable names. "
                "Follow PEP 8 strictly."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a user_manager.py module with add_user(name, email) and "
            "get_user(user_id) functions. Use a dict as in-memory storage.",
        )
        assert result.success, f"Production run failed: {result.error}"

        score = llm_score(result.final_response, PROMPT_QUALITY_RUBRIC)
        assert_score(score, min_pct=0.5)
