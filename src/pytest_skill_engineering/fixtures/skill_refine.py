"""Skill refinement fixture for Phase 3 of skill-creator workflow.

Provides the ``skill_refiner`` fixture that analyzes eval failures
and suggests SKILL.md improvements.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_skill_engineering.core.skill import Skill
from pytest_skill_engineering.core.skill_refiner import RefinementResult, analyze_skill_failures

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from pytest_skill_engineering.core.skill_eval_results import SkillGradingResult

logger = logging.getLogger(__name__)


@pytest.fixture
def skill_refiner(
    skill_eval_runner: Callable[..., Coroutine[Any, Any, SkillGradingResult]],
) -> Callable[..., Coroutine[Any, Any, RefinementResult]]:
    """Analyze skill eval failures and suggest improvements.

    Phase 3 of the skill-creator workflow: runs skill evals, analyzes
    failures, and suggests specific improvements to SKILL.md.

    Example:
        async def test_refine_skill(skill_refiner):
            result = await skill_refiner("skills/my-skill/")
            assert result.suggestions  # Got improvement ideas
            print(result.summary)

    Args:
        skill_eval_runner: The skill_eval_runner fixture

    Returns:
        Async function that runs refinement analysis
    """

    async def run(
        skill_path: str | Path,
        *,
        model: str | None = None,
    ) -> RefinementResult:
        """Run skill evals and analyze failures for improvement suggestions.

        Args:
            skill_path: Path to skill directory containing evals/evals.json
            model: Optional model override for the LLM analysis

        Returns:
            RefinementResult with suggested improvements

        Raises:
            FileNotFoundError: If skill or evals/evals.json doesn't exist
            ValueError: If evals.json format is invalid
        """
        skill_path = Path(skill_path)

        # 1. Load the skill
        skill = Skill.from_path(skill_path)

        # 2. Run evals via skill_eval_runner
        logger.info("Running evals for skill: %s", skill.metadata.name)
        grading_result = await skill_eval_runner(skill_path, model=model)

        # 3. If all passed, return empty suggestions
        if grading_result.all_passed:
            logger.info("All evals passed — no refinement needed")
            return RefinementResult(
                skill_name=skill.metadata.name,
                suggestions=[],
                summary="All evaluations passed — no improvements needed.",
                failures_analyzed=0,
                pass_rate_before=1.0,
            )

        # 4. Call analyze_skill_failures
        logger.info(
            "Pass rate: %.1f%% — analyzing failures...",
            grading_result.pass_rate * 100,
        )
        result = await analyze_skill_failures(skill, grading_result, model=model)

        logger.info("Refinement analysis complete: %d suggestions", len(result.suggestions))
        return result

    return run


__all__ = ["skill_refiner"]
