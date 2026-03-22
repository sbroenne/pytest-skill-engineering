"""Level 14 — Skill-creator eval automation.

Tests the skill_eval_runner fixture that auto-discovers evals from skill
directories, runs them via CopilotEval, validates expectations with llm_assert,
and exports grading.json.

This is the bridge between Anthropic's skill-creator interactive authoring
and our CI/CD testing pipeline.

Run with: pytest tests/integration/copilot/test_14_skill_evals.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.copilot]


class TestSkillCreatorAutomation:
    """Full skill-creator eval pipeline."""

    async def test_run_skill_evals(self, skill_eval_runner):
        """Run all evals for math-helper skill.

        The math-helper skill has 2 eval cases in evals/evals.json:
        1. Compound interest calculation
        2. Derivative of a polynomial

        This test verifies that:
        - All evals are discovered and run
        - Grading structure is skill-creator compatible
        - Results are returned with proper typing
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_eval_runner(skill_path)

        # Verify grading structure
        assert "summary" in result.grading
        assert "expectations" in result.grading
        assert "execution_metrics" in result.grading

        # Verify we ran both cases
        assert result.grading["summary"]["total"] >= 2, "Should have at least 2 expectations"
        assert len(result.cases) == 2, "Should have 2 eval cases"

        # Verify case structure
        for case in result.cases:
            assert case.case.id in (1, 2)
            assert case.case.prompt
            assert isinstance(case.expectation_results, list)
            assert isinstance(case.evidence, list)
            assert isinstance(case.passed, bool)

    async def test_grading_export(self, skill_eval_runner, tmp_path):
        """Verify grading.json export is skill-creator compatible.

        Tests that:
        - grading.json is written to the specified path
        - The JSON structure matches skill-creator's schema
        - All required fields are present
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        grading_file = tmp_path / "grading.json"

        result = await skill_eval_runner(
            skill_path,
            export_grading_path=grading_file,
        )

        # Verify file was written
        assert grading_file.exists(), "grading.json should be written"

        import json

        grading = json.loads(grading_file.read_text())

        # Verify required top-level keys
        assert "summary" in grading
        assert "expectations" in grading
        assert "execution_metrics" in grading
        assert "cases" in grading

        # Verify summary structure
        summary = grading["summary"]
        assert "passed" in summary
        assert "failed" in summary
        assert "total" in summary
        assert "pass_rate" in summary
        assert summary["passed"] + summary["failed"] == summary["total"]

        # Verify expectations structure
        expectations = grading["expectations"]
        assert isinstance(expectations, list)
        assert len(expectations) > 0
        for exp in expectations:
            assert "text" in exp
            assert "passed" in exp
            assert "evidence" in exp

        # Verify execution_metrics
        metrics = grading["execution_metrics"]
        assert "tool_calls" in metrics
        assert "turns" in metrics
        assert "duration_ms" in metrics
        assert "success" in metrics

        # Verify cases structure
        cases = grading["cases"]
        assert isinstance(cases, list)
        assert len(cases) == 2
        for case in cases:
            assert "id" in case
            assert "name" in case
            assert "prompt" in case
            assert "passed" in case
            assert "expectations" in case
            assert isinstance(case["expectations"], list)

    async def test_skill_grading_result_properties(self, skill_eval_runner):
        """Verify SkillGradingResult convenience properties.

        Tests that:
        - pass_rate returns correct percentage
        - all_passed returns correct boolean
        - skill_name is extracted correctly
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        result = await skill_eval_runner(skill_path)

        # Verify pass_rate is a float between 0 and 1
        assert 0.0 <= result.pass_rate <= 1.0
        assert isinstance(result.pass_rate, float)

        # Verify all_passed is a boolean
        assert isinstance(result.all_passed, bool)

        # Verify skill_name
        assert result.skill_name == "math-helper"

        # Verify consistency between all_passed and pass_rate
        if result.all_passed:
            assert result.pass_rate == 1.0
        else:
            assert result.pass_rate < 1.0

    async def test_working_directory_override(self, skill_eval_runner, tmp_path):
        """Verify working_directory parameter works.

        Tests that the CopilotEval's working directory can be overridden
        via the skill_eval_runner fixture.
        """
        skill_path = Path(__file__).parent.parent / "skills" / "math-helper"
        custom_workdir = tmp_path / "custom_workspace"
        custom_workdir.mkdir()

        result = await skill_eval_runner(
            skill_path,
            working_directory=custom_workdir,
        )

        # Should complete without error
        assert result.cases, "Should have case results"
        assert result.skill_name == "math-helper"
