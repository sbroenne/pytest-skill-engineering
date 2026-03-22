"""Skill benchmarking — with_skill vs without_skill comparison.

Phase 4 of the skill-creator workflow: measure the measurable impact
of a skill by running the same evals with and without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pytest_skill_engineering.core.skill_evals import SkillEvalCase


@dataclass(slots=True, frozen=True)
class BenchmarkComparison:
    """Comparison of a single expectation across baseline and treatment.

    Attributes:
        expectation: The expectation text that was validated
        baseline_passed: Whether this expectation passed without the skill
        treatment_passed: Whether this expectation passed with the skill
        delta: Change status: "improved", "regressed", or "unchanged"
    """

    expectation: str
    baseline_passed: bool
    treatment_passed: bool
    delta: str

    def __post_init__(self) -> None:
        """Validate delta value."""
        if self.delta not in {"improved", "regressed", "unchanged"}:
            raise ValueError(
                f"delta must be 'improved', 'regressed', or 'unchanged', got {self.delta!r}"
            )


@dataclass(slots=True)
class CaseBenchmark:
    """Benchmark results for a single eval case.

    Attributes:
        case: The eval case that was benchmarked
        baseline_passed: Whether all expectations passed without the skill
        treatment_passed: Whether all expectations passed with the skill
        comparisons: Per-expectation comparison results
        baseline_duration_ms: Execution time without skill
        treatment_duration_ms: Execution time with skill
        baseline_tool_calls: Number of tool calls without skill
        treatment_tool_calls: Number of tool calls with skill
    """

    case: SkillEvalCase
    baseline_passed: bool
    treatment_passed: bool
    comparisons: list[BenchmarkComparison]
    baseline_duration_ms: float
    treatment_duration_ms: float
    baseline_tool_calls: int
    treatment_tool_calls: int


@dataclass(slots=True)
class SkillBenchmarkResult:
    """Full benchmark comparing skill vs no-skill performance.

    Attributes:
        skill_name: Name of the skill being benchmarked
        cases: Per-case benchmark results
        baseline_grading: grading.json dict without skill
        treatment_grading: grading.json dict with skill
    """

    skill_name: str
    cases: list[CaseBenchmark]
    baseline_grading: dict[str, Any]
    treatment_grading: dict[str, Any]

    @property
    def baseline_pass_rate(self) -> float:
        """Pass rate without the skill (0.0 to 1.0)."""
        if not self.cases:
            return 0.0
        passed = sum(1 for c in self.cases if c.baseline_passed)
        return passed / len(self.cases)

    @property
    def treatment_pass_rate(self) -> float:
        """Pass rate with the skill (0.0 to 1.0)."""
        if not self.cases:
            return 0.0
        passed = sum(1 for c in self.cases if c.treatment_passed)
        return passed / len(self.cases)

    @property
    def improvement(self) -> float:
        """Pass rate delta: treatment - baseline.

        Positive means the skill helped, negative means it regressed.
        """
        return self.treatment_pass_rate - self.baseline_pass_rate

    @property
    def skill_helps(self) -> bool:
        """Whether the skill improved pass rate."""
        return self.improvement > 0

    @property
    def regressions(self) -> list[BenchmarkComparison]:
        """Expectations that passed without skill but failed with it."""
        all_comparisons: list[BenchmarkComparison] = []
        for case_bench in self.cases:
            all_comparisons.extend(case_bench.comparisons)
        return [c for c in all_comparisons if c.delta == "regressed"]

    @property
    def improvements(self) -> list[BenchmarkComparison]:
        """Expectations that failed without skill but passed with it."""
        all_comparisons: list[BenchmarkComparison] = []
        for case_bench in self.cases:
            all_comparisons.extend(case_bench.comparisons)
        return [c for c in all_comparisons if c.delta == "improved"]

    def summary(self) -> str:
        """Human-readable benchmark summary."""
        baseline_pct = self.baseline_pass_rate * 100
        treatment_pct = self.treatment_pass_rate * 100
        improvement_pct = self.improvement * 100

        lines = [
            f"Skill Benchmark: {self.skill_name}",
            f"Cases: {len(self.cases)}",
            f"Baseline (no skill): {baseline_pct:.1f}% pass rate",
            f"Treatment (with skill): {treatment_pct:.1f}% pass rate",
            f"Improvement: {improvement_pct:+.1f}%",
        ]

        if self.improvements:
            lines.append(f"✅ Improvements: {len(self.improvements)} expectation(s)")
        if self.regressions:
            lines.append(f"❌ Regressions: {len(self.regressions)} expectation(s)")

        if self.skill_helps:
            lines.append("🎯 Verdict: Skill helps")
        elif self.improvement < 0:
            lines.append("⚠️  Verdict: Skill regresses performance")
        else:
            lines.append("➖ Verdict: No measurable impact")

        return "\n".join(lines)


__all__ = [
    "BenchmarkComparison",
    "CaseBenchmark",
    "SkillBenchmarkResult",
]
