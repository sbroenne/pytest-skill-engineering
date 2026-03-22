"""Skill benchmark fixture for Phase 4 of skill-creator workflow.

Compares with_skill vs without_skill performance on the same evals to
measure the statistical impact of a skill.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.core.skill import Skill
from pytest_skill_engineering.core.skill_benchmark import (
    BenchmarkComparison,
    CaseBenchmark,
    SkillBenchmarkResult,
)
from pytest_skill_engineering.core.skill_evals import load_skill_evals
from pytest_skill_engineering.core.skill_grading import export_grading

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from pytest_skill_engineering.copilot.result import CopilotResult


@pytest.fixture
def skill_benchmark(
    copilot_eval: Callable[[CopilotEval, str], Coroutine[Any, Any, CopilotResult]],
    llm_assert: Callable[[str, str], bool],
    tmp_path: Path,
) -> Callable[..., Coroutine[Any, Any, SkillBenchmarkResult]]:
    """Compare skill vs no-skill performance on the same evals.

    Phase 4 of the skill-creator workflow: run each eval case twice
    (once without the skill, once with) and measure the improvement.

    Example:
        async def test_skill_value(skill_benchmark):
            result = await skill_benchmark("skills/my-skill/")
            assert result.skill_helps
            assert result.improvement > 0.1  # At least 10% improvement
            assert not result.regressions  # No regressions

    Args:
        copilot_eval: The copilot_eval fixture for running agents
        llm_assert: The llm_assert fixture for semantic assertions
        tmp_path: pytest's tmp_path fixture (used for default working dir)

    Returns:
        Async function that benchmarks a skill and returns SkillBenchmarkResult
    """

    async def run(
        skill_path: str | Path,
        *,
        model: str | None = None,
        instructions: str = "",
        working_directory: str | Path | None = None,
    ) -> SkillBenchmarkResult:
        """Benchmark a skill by comparing with vs without performance.

        Args:
            skill_path: Path to skill directory containing evals/evals.json
            model: Optional model override (defaults to Copilot's default)
            instructions: Base instructions for both baseline and treatment
            working_directory: Optional working directory for the eval
                (defaults to tmp_path if not provided)

        Returns:
            SkillBenchmarkResult with comparison data and grading.json dicts

        Raises:
            FileNotFoundError: If skill or evals/evals.json doesn't exist
            ValueError: If evals.json format is invalid or no cases found
        """
        skill_path = Path(skill_path)

        # 1. Load the skill and eval cases
        skill = Skill.from_path(skill_path)
        cases = load_skill_evals(skill_path)
        if not cases:
            raise ValueError(f"No eval cases found in {skill_path / 'evals' / 'evals.json'}")

        work_dir = str(working_directory or tmp_path)

        # 2. Create baseline agent (NO skill_directories)
        baseline_agent = CopilotEval(
            name=f"{skill.metadata.name or 'skill'}-baseline",
            model=model,
            instructions=instructions,
            working_directory=work_dir,
        )

        # 3. Create treatment agent (WITH skill_directories)
        treatment_agent = CopilotEval(
            name=f"{skill.metadata.name or 'skill'}-treatment",
            model=model,
            instructions=instructions,
            skill_directories=[str(skill_path)],
            working_directory=work_dir,
        )

        # 4. Run each case on BOTH agents (baseline first, then treatment)
        case_benchmarks: list[CaseBenchmark] = []
        baseline_all_expectations: list[str] = []
        baseline_all_results: list[bool] = []
        treatment_all_expectations: list[str] = []
        treatment_all_results: list[bool] = []

        # Keep track of last results for grading export
        last_baseline_result: CopilotResult | None = None
        last_treatment_result: CopilotResult | None = None

        for case in cases:
            # Run baseline (without skill)
            baseline_result = await copilot_eval(baseline_agent, case.prompt)
            last_baseline_result = baseline_result
            baseline_expectations: list[bool] = []
            for expectation in case.expectations:
                passed = bool(llm_assert(baseline_result.final_response or "", expectation))
                baseline_expectations.append(passed)
                baseline_all_expectations.append(expectation)
                baseline_all_results.append(passed)

            # Run treatment (with skill)
            treatment_result = await copilot_eval(treatment_agent, case.prompt)
            last_treatment_result = treatment_result
            treatment_expectations: list[bool] = []
            for expectation in case.expectations:
                passed = bool(llm_assert(treatment_result.final_response or "", expectation))
                treatment_expectations.append(passed)
                treatment_all_expectations.append(expectation)
                treatment_all_results.append(passed)

            # Build per-expectation comparisons
            comparisons: list[BenchmarkComparison] = []
            for exp_text, baseline_pass, treatment_pass in zip(
                case.expectations,
                baseline_expectations,
                treatment_expectations,
                strict=True,
            ):
                if baseline_pass == treatment_pass:
                    delta = "unchanged"
                elif treatment_pass and not baseline_pass:
                    delta = "improved"
                else:
                    delta = "regressed"

                comparisons.append(
                    BenchmarkComparison(
                        expectation=exp_text,
                        baseline_passed=baseline_pass,
                        treatment_passed=treatment_pass,
                        delta=delta,
                    )
                )

            # Build case-level benchmark
            case_benchmarks.append(
                CaseBenchmark(
                    case=case,
                    baseline_passed=all(baseline_expectations),
                    treatment_passed=all(treatment_expectations),
                    comparisons=comparisons,
                    baseline_duration_ms=baseline_result.duration_ms,
                    treatment_duration_ms=treatment_result.duration_ms,
                    baseline_tool_calls=len(baseline_result.all_tool_calls),
                    treatment_tool_calls=len(treatment_result.all_tool_calls),
                )
            )

        # 5. Export grading.json for baseline and treatment
        # Use the last result for execution metrics
        if last_baseline_result is None or last_treatment_result is None:
            raise ValueError("No results to export - no cases were run")

        baseline_grading = export_grading(
            last_baseline_result,
            baseline_all_expectations,
            baseline_all_results,
        )

        treatment_grading = export_grading(
            last_treatment_result,
            treatment_all_expectations,
            treatment_all_results,
        )

        return SkillBenchmarkResult(
            skill_name=skill.metadata.name or "unknown",
            cases=case_benchmarks,
            baseline_grading=baseline_grading,
            treatment_grading=treatment_grading,
        )

    return run


__all__ = ["skill_benchmark"]
