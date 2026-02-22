"""Multi-dimension LLM scoring fixture.

Provides the ``llm_score`` fixture for evaluating text against a structured
rubric with multiple named dimensions, each scored on a configurable scale.

Built on pydantic-ai for structured output extraction — the judge LLM returns
typed per-dimension scores rather than free-text JSON that requires manual
parsing.

Complements ``llm_assert`` (single-criterion pass/fail) with granular,
multi-dimension numeric evaluation suitable for quality regression testing
and A/B comparisons.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

_LLM_MODEL_DEFAULT = "openai/gpt-5-mini"


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ScoringDimension:
    """A single dimension in a scoring rubric.

    Attributes:
        name: Short identifier (e.g. ``"accuracy"``).
        description: What this dimension measures and how to score it.
        max_score: Upper bound of the scale (default 5).  The minimum is
            always 1.
        weight: Relative weight for composite score calculation (default 1.0).
    """

    name: str
    description: str
    max_score: int = 5
    weight: float = 1.0


@dataclass(slots=True)
class ScoreResult:
    """Structured result from a multi-dimension LLM evaluation.

    Attributes:
        scores: Per-dimension scores keyed by dimension name.
        total: Sum of all dimension scores.
        max_total: Maximum possible total score.
        weighted_score: Weighted composite score (0.0 – 1.0).
        reasoning: Free-text explanation from the judge.
    """

    scores: dict[str, int]
    total: int
    max_total: int
    weighted_score: float
    reasoning: str

    def __repr__(self) -> str:
        pct = f"{self.weighted_score:.0%}"
        dims = ", ".join(f"{k}={v}" for k, v in self.scores.items())
        return (
            f"ScoreResult({self.total}/{self.max_total} [{pct}]: {dims})\n"
            f"  Reasoning: {self.reasoning}"
        )


# ---------------------------------------------------------------------------
# Pydantic model for structured judge output
# ---------------------------------------------------------------------------


class _DimensionScore(BaseModel):
    """A single dimension's score returned by the judge."""

    name: str = Field(description="Dimension name exactly as given in the rubric")
    score: int = Field(description="Integer score for this dimension")
    justification: str = Field(description="Brief justification for this score")


class _JudgeOutput(BaseModel):
    """Structured output from the multi-dimension judge."""

    dimensions: list[_DimensionScore] = Field(
        description="One entry per rubric dimension, in the same order"
    )
    reasoning: str = Field(description="Overall reasoning about the content quality")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_scoring_prompt(
    content: str,
    rubric: list[ScoringDimension],
    *,
    content_label: str = "content",
    context: str | None = None,
) -> str:
    """Build the evaluation prompt for the judge LLM."""
    dimension_lines = "\n".join(
        f"{i}. **{d.name}** (1–{d.max_score}): {d.description}" for i, d in enumerate(rubric, 1)
    )

    context_block = ""
    if context:
        context_block = f"\n## Context\n{context}\n"

    return (
        f"You are an expert evaluator. Rate the following {content_label} on "
        f"each dimension using the specified scale.\n"
        f"{context_block}\n"
        f"## Rubric\n{dimension_lines}\n\n"
        f"## {content_label.capitalize()} to evaluate\n"
        f"---\n{content}\n---\n\n"
        f"Score each dimension independently. Be strict and calibrated — "
        f"reserve top scores for genuinely excellent work."
    )


# ---------------------------------------------------------------------------
# Core scoring logic
# ---------------------------------------------------------------------------


async def _run_judge(
    content: str,
    rubric: list[ScoringDimension],
    *,
    model: Any,
    content_label: str = "content",
    context: str | None = None,
) -> ScoreResult:
    """Call the judge LLM and return structured scores."""
    from pydantic_ai import Agent

    prompt = _build_scoring_prompt(content, rubric, content_label=content_label, context=context)

    agent: Agent[None, _JudgeOutput] = Agent(
        model,
        output_type=_JudgeOutput,
        instructions=(
            "You are an expert content evaluator. Evaluate the content "
            "against each rubric dimension and return structured scores."
        ),
    )

    result = await agent.run(prompt)
    output = result.output

    # Map dimension scores by name
    score_map: dict[str, int] = {}
    for dim_score in output.dimensions:
        score_map[dim_score.name] = dim_score.score

    # Ensure all rubric dimensions are present, default to 0 if missing
    scores: dict[str, int] = {}
    for dim in rubric:
        raw = score_map.get(dim.name, 0)
        # Clamp to valid range
        scores[dim.name] = max(1, min(raw, dim.max_score))

    total = sum(scores.values())
    max_total = sum(d.max_score for d in rubric)

    # Weighted composite: each dimension contributes proportionally
    weighted_sum = sum((scores[d.name] / d.max_score) * d.weight for d in rubric)
    weight_total = sum(d.weight for d in rubric)
    weighted_score = weighted_sum / weight_total if weight_total > 0 else 0.0

    return ScoreResult(
        scores=scores,
        total=total,
        max_total=max_total,
        weighted_score=weighted_score,
        reasoning=output.reasoning,
    )


# ---------------------------------------------------------------------------
# Fixture callable
# ---------------------------------------------------------------------------


class LLMScore:
    """Callable that evaluates content against a multi-dimension rubric.

    Uses pydantic-ai with structured output to extract per-dimension scores
    from a judge LLM.

    Example::

        def test_plan_quality(llm_score):
            rubric = [
                ScoringDimension("accuracy", "Factually correct", max_score=5),
                ScoringDimension("completeness", "Covers all points", max_score=5),
            ]
            result = llm_score(plan_text, rubric)
            assert result.total >= 7
    """

    def __init__(self, model: Any) -> None:
        self._model = model

    def __call__(
        self,
        content: str,
        rubric: list[ScoringDimension],
        *,
        content_label: str = "content",
        context: str | None = None,
    ) -> ScoreResult:
        """Evaluate content against a multi-dimension rubric.

        Args:
            content: The text to evaluate.
            rubric: List of ScoringDimension definitions.
            content_label: How to describe the content to the judge
                (e.g. ``"implementation plan"``, ``"code review"``).
            context: Optional background context for the judge
                (e.g. the original task prompt, source code).

        Returns:
            ScoreResult with per-dimension scores and reasoning.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run,
                _run_judge(
                    content,
                    rubric,
                    model=self._model,
                    content_label=content_label,
                    context=context,
                ),
            ).result()

    async def async_score(
        self,
        content: str,
        rubric: list[ScoringDimension],
        *,
        content_label: str = "content",
        context: str | None = None,
    ) -> ScoreResult:
        """Async variant for use in async test functions.

        Same parameters as ``__call__``.
        """
        return await _run_judge(
            content,
            rubric,
            model=self._model,
            content_label=content_label,
            context=context,
        )


# ---------------------------------------------------------------------------
# Assertion helper
# ---------------------------------------------------------------------------


def assert_score(
    result: ScoreResult,
    *,
    min_total: int | None = None,
    min_pct: float | None = None,
    min_dimensions: dict[str, int] | None = None,
) -> None:
    """Assert that judge scores meet minimum thresholds.

    Args:
        result: ScoreResult from an LLMScore evaluation.
        min_total: Minimum total score (sum of all dimensions).
        min_pct: Minimum weighted percentage (0.0 – 1.0).
        min_dimensions: Per-dimension minimum scores keyed by name.

    Raises:
        AssertionError: If any threshold is not met.
    """
    if min_total is not None:
        assert result.total >= min_total, (
            f"Total score {result.total}/{result.max_total} below minimum "
            f"{min_total}. Scores: {result.scores}. "
            f"Reasoning: {result.reasoning}"
        )

    if min_pct is not None:
        assert result.weighted_score >= min_pct, (
            f"Weighted score {result.weighted_score:.1%} below minimum "
            f"{min_pct:.1%}. Scores: {result.scores}. "
            f"Reasoning: {result.reasoning}"
        )

    if min_dimensions:
        for dim, minimum in min_dimensions.items():
            actual = result.scores.get(dim, 0)
            assert actual >= minimum, (
                f"Dimension '{dim}' scored {actual}, minimum is {minimum}. "
                f"Reasoning: {result.reasoning}"
            )


# ---------------------------------------------------------------------------
# Pytest fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_score(request: pytest.FixtureRequest) -> LLMScore:
    """Fixture providing multi-dimension LLM scoring.

    Evaluates text content against a structured rubric with multiple named
    dimensions. Each dimension receives an integer score on a configurable
    scale. Returns a ``ScoreResult`` with per-dimension scores, totals,
    and weighted composite score.

    The judge model is resolved in this order:

    1. ``--llm-model`` if explicitly set
    2. ``--aitest-summary-model`` (shared analysis model)
    3. ``openai/gpt-5-mini`` as final fallback

    Example::

        from pytest_skill_engineering.fixtures.llm_score import ScoringDimension, assert_score

        def test_quality(llm_score):
            rubric = [
                ScoringDimension("accuracy", "Factually correct"),
                ScoringDimension("clarity", "Easy to understand"),
            ]
            result = llm_score(my_text, rubric)
            assert_score(result, min_total=7)
    """
    from pytest_skill_engineering.fixtures.llm_assert import _build_judge_model

    model_str: str = request.config.getoption("--llm-model")
    if model_str == _LLM_MODEL_DEFAULT:
        summary_model = request.config.getoption("--aitest-summary-model", default=None)
        if summary_model:
            model_str = summary_model
    model = _build_judge_model(model_str)
    return LLMScore(model=model)
