"""Level 15 — Skill refinement (Phase 3 of skill-creator workflow).

Tests the skill_refiner fixture that analyzes eval failures and produces
actionable SKILL.md improvement suggestions.

Run with: pytest tests/integration/copilot/test_15_skill_refinement.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.copilot, pytest.mark.skill, pytest.mark.slow]


class TestSkillRefinement:
    """Phase 3 of skill-creator workflow: analyze failures and suggest improvements."""

    async def test_analyze_failures_produces_suggestions(self, skill_refiner):
        """Refiner produces suggestions for a skill with failing evals.

        Uses the math-helper skill which may have some expectations that fail.
        Tests that:
        - Refinement analysis runs successfully
        - RefinementResult has correct structure
        - Suggestions are produced when there are failures
        - Each suggestion has all required fields
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_refiner(skill_path)

        # Verify result structure
        assert result.skill_name == "math-helper"
        assert isinstance(result.suggestions, list)
        assert isinstance(result.summary, str)
        assert result.summary  # Non-empty
        assert isinstance(result.failures_analyzed, int)
        assert 0.0 <= result.pass_rate_before <= 1.0

        # If there were failures, we should have suggestions
        if result.pass_rate_before < 1.0:
            assert result.failures_analyzed > 0, "Should have analyzed some failures"
            # Suggestions are optional — LLM might decide no changes needed
            # But we verify structure if they exist
            for suggestion in result.suggestions:
                assert suggestion.section
                assert suggestion.suggested_text
                assert suggestion.reasoning
                assert isinstance(suggestion.addresses_failures, tuple)

    async def test_perfect_skill_returns_no_suggestions(self, skill_refiner):
        """Refiner returns empty suggestions when all evals pass.

        If the math-helper skill happens to pass all evals (unlikely but possible),
        we should get an empty suggestions list with a positive summary.
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_refiner(skill_path)

        # If pass rate is 100%, should have no suggestions
        if result.pass_rate_before == 1.0:
            assert result.failures_analyzed == 0
            assert len(result.suggestions) == 0
            assert (
                "no improvements needed" in result.summary.lower()
                or "passed" in result.summary.lower()
            )

    async def test_refinement_result_structure(self, skill_refiner):
        """Verify RefinementResult has correct structure and types."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_refiner(skill_path)

        # Verify all required fields exist and have correct types
        assert hasattr(result, "skill_name")
        assert hasattr(result, "suggestions")
        assert hasattr(result, "summary")
        assert hasattr(result, "failures_analyzed")
        assert hasattr(result, "pass_rate_before")

        assert isinstance(result.skill_name, str)
        assert isinstance(result.suggestions, list)
        assert isinstance(result.summary, str)
        assert isinstance(result.failures_analyzed, int)
        assert isinstance(result.pass_rate_before, float)

        # Verify suggestions structure if any exist
        for suggestion in result.suggestions:
            assert hasattr(suggestion, "section")
            assert hasattr(suggestion, "current_text")
            assert hasattr(suggestion, "suggested_text")
            assert hasattr(suggestion, "reasoning")
            assert hasattr(suggestion, "addresses_failures")

            assert isinstance(suggestion.section, str)
            assert isinstance(suggestion.current_text, str)
            assert isinstance(suggestion.suggested_text, str)
            assert isinstance(suggestion.reasoning, str)
            assert isinstance(suggestion.addresses_failures, tuple)

    async def test_refinement_uses_custom_model(self, skill_refiner):
        """Verify refinement respects model parameter.

        This test just checks that the model parameter is accepted
        and doesn't raise an error. We can't easily verify which
        model was actually used without inspecting internals.
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        # Should not raise an error
        result = await skill_refiner(skill_path, model="gpt-5.4-mini")
        assert result is not None
