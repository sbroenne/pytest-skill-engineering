"""Core result types for skill-eval execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_skill_engineering.copilot.result import CopilotResult
    from pytest_skill_engineering.core.skill_evals import SkillEvalCase


@dataclass(slots=True)
class SkillCaseResult:
    """Result of running a single skill eval case."""

    case: SkillEvalCase
    result: CopilotResult
    expectation_results: list[bool]
    evidence: list[str]
    passed: bool


@dataclass(slots=True)
class SkillGradingResult:
    """Result of running all skill eval cases for a skill."""

    skill_name: str
    cases: list[SkillCaseResult]
    grading: dict[str, Any]

    @property
    def pass_rate(self) -> float:
        """Pass rate across all cases."""
        if not self.cases:
            return 0.0
        passed = sum(1 for case in self.cases if case.passed)
        return passed / len(self.cases)

    @property
    def all_passed(self) -> bool:
        """Whether all cases passed."""
        return all(case.passed for case in self.cases)


__all__ = ["SkillCaseResult", "SkillGradingResult"]
