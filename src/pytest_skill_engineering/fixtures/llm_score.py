"""Multi-dimension LLM scoring fixture.

Provides the ``llm_score`` fixture for evaluating text against a structured
rubric with multiple named dimensions, each scored on a configurable scale.

Uses the Copilot SDK for judge calls with structured prompt engineering to
extract per-dimension scores. Complements ``llm_assert`` (single-criterion
pass/fail) with granular, multi-dimension numeric evaluation suitable for
quality regression testing and A/B comparisons.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from dataclasses import dataclass

import pytest

_LLM_MODEL_DEFAULT = "copilot/gpt-5-mini"


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
        f"reserve top scores for genuinely excellent work.\n\n"
        f"Format your response as:\n"
        f"DIMENSION_NAME: SCORE - Justification\n"
        f"(repeat for each dimension)\n\n"
        f"OVERALL_REASONING: Your overall assessment\n"
    )


# ---------------------------------------------------------------------------
# Core scoring logic
# ---------------------------------------------------------------------------


async def _run_judge(
    content: str,
    rubric: list[ScoringDimension],
    *,
    model: str,
    content_label: str = "content",
    context: str | None = None,
) -> ScoreResult:
    """Call the judge LLM and return structured scores."""
    from pytest_skill_engineering.copilot.judge import copilot_judge  # noqa: PLC0415

    prompt = _build_scoring_prompt(content, rubric, content_label=content_label, context=context)

    # Strip model prefix if present (copilot/, azure/, openai/)
    judge_model = model
    if "/" in judge_model:
        judge_model = judge_model.split("/", 1)[1]

    response = await copilot_judge(prompt, model=judge_model, timeout_seconds=60.0)

    # Parse response to extract scores
    scores: dict[str, int] = {}
    reasoning_parts: list[str] = []

    # Pattern: DIMENSION_NAME: SCORE - Justification
    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("OVERALL_REASONING:"):
            reasoning_parts.append(line.split(":", 1)[1].strip())
            continue

        # Try to parse dimension score
        if ":" in line:
            parts = line.split(":", 1)
            dim_name = parts[0].strip()
            rest = parts[1].strip()

            # Extract score (should be first number)
            score_match = re.search(r"\b(\d+)\b", rest)
            if score_match:
                score = int(score_match.group(1))

                # Match against rubric dimensions
                for dim in rubric:
                    if dim.name.lower() == dim_name.lower():
                        # Clamp to valid range
                        scores[dim.name] = max(1, min(score, dim.max_score))
                        break

    # Ensure all rubric dimensions are present, default to 1 if missing
    for dim in rubric:
        if dim.name not in scores:
            scores[dim.name] = 1

    total = sum(scores.values())
    max_total = sum(d.max_score for d in rubric)

    # Weighted composite: each dimension contributes proportionally
    weighted_sum = sum((scores[d.name] / d.max_score) * d.weight for d in rubric)
    weight_total = sum(d.weight for d in rubric)
    weighted_score = weighted_sum / weight_total if weight_total > 0 else 0.0

    reasoning = " ".join(reasoning_parts) if reasoning_parts else "No overall reasoning provided"

    return ScoreResult(
        scores=scores,
        total=total,
        max_total=max_total,
        weighted_score=weighted_score,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Fixture callable
# ---------------------------------------------------------------------------


class LLMScore:
    """Callable that evaluates content against a multi-dimension rubric.

    Uses the Copilot SDK with structured prompting to extract per-dimension
    scores from a judge LLM.

    Example::

        def test_plan_quality(llm_score):
            rubric = [
                ScoringDimension("accuracy", "Factually correct", max_score=5),
                ScoringDimension("completeness", "Covers all points", max_score=5),
            ]
            result = llm_score(plan_text, rubric)
            assert result.total >= 7
    """

    def __init__(self, model: str) -> None:
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
    3. ``copilot/gpt-5-mini`` as final fallback

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
    model_str: str = request.config.getoption("--llm-model")
    if model_str == "openai/gpt-5-mini":  # Old default
        model_str = _LLM_MODEL_DEFAULT
    if model_str == _LLM_MODEL_DEFAULT:
        summary_model = request.config.getoption("--aitest-summary-model", default=None)
        if summary_model:
            model_str = summary_model
    return LLMScore(model=model_str)
