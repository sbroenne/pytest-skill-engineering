"""Test skill benchmarking (Phase 4 of skill-creator workflow).

Tests that the skill_benchmark fixture correctly compares
with_skill vs without_skill performance on the same evals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.copilot, pytest.mark.skill, pytest.mark.slow]


class TestSkillBenchmark:
    """Test the skill_benchmark fixture for Phase 4 workflow."""

    async def test_benchmark_produces_comparison(self, skill_benchmark):
        """Benchmark produces baseline vs treatment comparison."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(skill_path)

        # Verify basic structure
        assert len(result.cases) == 2  # math-helper has 2 evals
        assert 0.0 <= result.baseline_pass_rate <= 1.0
        assert 0.0 <= result.treatment_pass_rate <= 1.0
        assert isinstance(result.improvement, float)
        assert result.skill_name == "math-helper"

    async def test_benchmark_result_structure(self, skill_benchmark):
        """Verify benchmark result has correct structure."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(skill_path)

        # Check grading dicts
        assert "summary" in result.baseline_grading
        assert "summary" in result.treatment_grading
        assert "expectations" in result.baseline_grading
        assert "expectations" in result.treatment_grading

        # Check case details
        for case in result.cases:
            assert isinstance(case.baseline_passed, bool)
            assert isinstance(case.treatment_passed, bool)
            assert case.baseline_duration_ms >= 0
            assert case.treatment_duration_ms >= 0
            assert case.baseline_tool_calls >= 0
            assert case.treatment_tool_calls >= 0
            assert len(case.comparisons) == len(case.case.expectations)

    async def test_benchmark_comparisons(self, skill_benchmark):
        """Verify per-expectation comparison structure."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(skill_path)

        # Check that comparisons have correct delta values
        for case in result.cases:
            for comp in case.comparisons:
                assert comp.expectation
                assert isinstance(comp.baseline_passed, bool)
                assert isinstance(comp.treatment_passed, bool)
                assert comp.delta in {"improved", "regressed", "unchanged"}

                # Verify delta logic
                if comp.baseline_passed == comp.treatment_passed:
                    assert comp.delta == "unchanged"
                elif comp.treatment_passed and not comp.baseline_passed:
                    assert comp.delta == "improved"
                else:
                    assert comp.delta == "regressed"

    async def test_benchmark_summary(self, skill_benchmark):
        """Benchmark produces human-readable summary."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(skill_path)

        summary = result.summary()
        assert result.skill_name in summary
        assert "%" in summary  # Contains pass rates
        assert "Baseline" in summary
        assert "Treatment" in summary
        assert "Improvement" in summary

        # Verify verdict line present
        assert any(
            verdict in summary
            for verdict in ["Skill helps", "No measurable impact", "regresses performance"]
        )

    async def test_benchmark_properties(self, skill_benchmark):
        """Test computed properties on benchmark result."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(skill_path)

        # Test pass rate properties
        assert result.improvement == result.treatment_pass_rate - result.baseline_pass_rate

        # Test skill_helps property
        if result.improvement > 0:
            assert result.skill_helps
        else:
            assert not result.skill_helps

        # Test improvements/regressions lists
        assert isinstance(result.improvements, list)
        assert isinstance(result.regressions, list)

        # Verify filtering logic
        for imp in result.improvements:
            assert imp.delta == "improved"
        for reg in result.regressions:
            assert reg.delta == "regressed"

    @pytest.mark.slow
    async def test_benchmark_with_custom_model(self, skill_benchmark):
        """Benchmark works with custom model specification."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(skill_path, model="gpt-5.4-mini")

        assert len(result.cases) > 0
        assert result.skill_name == "math-helper"

    @pytest.mark.slow
    async def test_benchmark_with_instructions(self, skill_benchmark):
        """Benchmark works with base instructions for both runs."""
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_benchmark(
            skill_path,
            instructions="You are a helpful assistant. Be concise.",
        )

        assert len(result.cases) == 2
        # Both baseline and treatment should use the same base instructions
        # (but treatment also gets skill context)
