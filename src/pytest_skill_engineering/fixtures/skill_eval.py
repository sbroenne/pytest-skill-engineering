"""Skill-creator eval automation fixture.

Provides the ``skill_eval_runner`` fixture that auto-discovers evals from
skill directories, runs them via CopilotEval, validates expectations with
llm_assert, and exports grading.json.

This is the bridge between Anthropic's skill-creator interactive authoring
and our CI/CD testing pipeline.

Example:
    async def test_run_skill_evals(skill_eval_runner):
        skill_path = Path("skills/my-skill/")
        result = await skill_eval_runner(skill_path)
        assert result.all_passed
        assert result.pass_rate >= 0.8
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.core.skill import Skill
from pytest_skill_engineering.core.skill_evals import SkillEvalCase, load_skill_evals
from pytest_skill_engineering.core.skill_grading import export_grading

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from pytest_skill_engineering.copilot.result import CopilotResult


@dataclass(slots=True)
class SkillCaseResult:
    """Result of running a single skill eval case.

    Attributes:
        case: The eval case that was run
        result: The CopilotResult from running the eval
        expectation_results: Whether each expectation passed
        evidence: Evidence strings for each expectation
        passed: Whether all expectations passed
    """

    case: SkillEvalCase
    result: CopilotResult
    expectation_results: list[bool]
    evidence: list[str]
    passed: bool


@dataclass(slots=True)
class SkillGradingResult:
    """Result of running all skill-creator evals for a skill.

    Attributes:
        skill_name: Name of the skill
        cases: Results for each eval case
        grading: skill-creator compatible grading.json dict
    """

    skill_name: str
    cases: list[SkillCaseResult]
    grading: dict[str, Any]

    @property
    def pass_rate(self) -> float:
        """Pass rate across all cases."""
        if not self.cases:
            return 0.0
        passed = sum(1 for c in self.cases if c.passed)
        return passed / len(self.cases)

    @property
    def all_passed(self) -> bool:
        """Whether all cases passed."""
        return all(c.passed for c in self.cases)


@pytest.fixture
def skill_eval_runner(
    copilot_eval: Callable[[CopilotEval, str], Coroutine[Any, Any, CopilotResult]],
    llm_assert: Callable[[str, str], bool],
    tmp_path: Path,
) -> Callable[..., Coroutine[Any, Any, SkillGradingResult]]:
    """Run all skill-creator evals for a skill and export grading.json.

    This fixture automates the full skill-creator eval pipeline:
    1. Load the skill
    2. Discover evals/evals.json
    3. Create CopilotEval with the skill
    4. Run each eval case
    5. Validate expectations with llm_assert
    6. Export grading.json

    Example:
        async def test_run_skill_evals(skill_eval_runner):
            result = await skill_eval_runner("skills/math-helper/")
            assert result.all_passed
            assert result.grading["summary"]["total"] == 2

    Args:
        copilot_eval: The copilot_eval fixture from pytest_skill_engineering
        llm_assert: The llm_assert fixture for semantic assertions
        tmp_path: pytest's tmp_path fixture (used for default working dir)

    Returns:
        Async function that runs all evals for a skill and returns SkillGradingResult
    """

    async def run(
        skill_path: str | Path,
        *,
        model: str | None = None,
        export_grading_path: str | Path | None = None,
        working_directory: str | Path | None = None,
    ) -> SkillGradingResult:
        """Run all skill-creator evals for a skill.

        Args:
            skill_path: Path to skill directory containing evals/evals.json
            model: Optional model override (defaults to Copilot's default)
            export_grading_path: Optional path to export grading.json
            working_directory: Optional working directory for the eval
                (defaults to tmp_path if not provided)

        Returns:
            SkillGradingResult with all case results and grading.json

        Raises:
            FileNotFoundError: If skill or evals/evals.json doesn't exist
            ValueError: If evals.json format is invalid
        """
        skill_path = Path(skill_path)

        # 1. Load the skill
        skill = Skill.from_path(skill_path)

        # 2. Load eval cases
        cases = load_skill_evals(skill_path)
        if not cases:
            raise ValueError(f"No eval cases found in {skill_path / 'evals' / 'evals.json'}")

        # 3. Create CopilotEval with the skill
        agent = CopilotEval(
            name=f"{skill.metadata.name or 'skill'}-eval",
            model=model,
            skill_directories=[str(skill_path)],
            working_directory=str(working_directory or tmp_path),
        )

        # 4. Run each eval case and validate expectations
        case_results: list[SkillCaseResult] = []
        for case in cases:
            result = await copilot_eval(agent, case.prompt)

            # Validate each expectation with llm_assert
            expectation_results: list[bool] = []
            evidence: list[str] = []
            final_response = result.final_response or ""

            for expectation in case.expectations:
                passed = llm_assert(final_response, expectation)
                expectation_results.append(passed)
                # Use the final response as evidence
                evidence.append(final_response)

            case_passed = all(expectation_results)
            case_results.append(
                SkillCaseResult(
                    case=case,
                    result=result,
                    expectation_results=expectation_results,
                    evidence=evidence,
                    passed=case_passed,
                )
            )

        # 5. Export grading.json
        # Aggregate all expectations across all cases
        all_expectations: list[str] = []
        all_expectation_results: list[bool] = []
        all_evidence: list[str] = []
        for case_result in case_results:
            all_expectations.extend(case_result.case.expectations)
            all_expectation_results.extend(case_result.expectation_results)
            all_evidence.extend(case_result.evidence)

        # Use the first case's result for execution metrics (all cases use same agent)
        representative_result = case_results[0].result if case_results else None
        if representative_result is None:
            raise ValueError("No results to export")

        grading = export_grading(
            representative_result,
            all_expectations,
            all_expectation_results,
            all_evidence,
        )

        # Add case-level breakdown to grading
        grading["cases"] = [
            {
                "id": cr.case.id,
                "name": cr.case.name,
                "prompt": cr.case.prompt,
                "passed": cr.passed,
                "expectations": [
                    {
                        "text": exp,
                        "passed": res,
                        "evidence": ev,
                    }
                    for exp, res, ev in zip(
                        cr.case.expectations,
                        cr.expectation_results,
                        cr.evidence,
                        strict=True,
                    )
                ],
            }
            for cr in case_results
        ]

        # 6. Export to file if requested
        if export_grading_path is not None:
            grading_path = Path(export_grading_path)
            grading_path.parent.mkdir(parents=True, exist_ok=True)
            grading_path.write_text(json.dumps(grading, indent=2), encoding="utf-8")

        return SkillGradingResult(
            skill_name=skill.metadata.name or "unknown",
            cases=case_results,
            grading=grading,
        )

    return run


__all__ = ["SkillCaseResult", "SkillGradingResult", "skill_eval_runner"]
