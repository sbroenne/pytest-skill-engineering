"""Core scoring types and assertion helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScoringDimension:
    """A single dimension in a scoring rubric."""

    name: str
    description: str
    max_score: int = 5
    weight: float = 1.0


@dataclass(slots=True)
class ScoreResult:
    """Structured result from a multi-dimension LLM evaluation."""

    scores: dict[str, int]
    total: int
    max_total: int
    weighted_score: float
    reasoning: str

    def __repr__(self) -> str:
        pct = f"{self.weighted_score:.0%}"
        dims = ", ".join(f"{key}={value}" for key, value in self.scores.items())
        return (
            f"ScoreResult({self.total}/{self.max_total} [{pct}]: {dims})\n"
            f"  Reasoning: {self.reasoning}"
        )


def assert_score(
    result: ScoreResult,
    *,
    min_total: int | None = None,
    min_pct: float | None = None,
    min_dimensions: dict[str, int] | None = None,
) -> None:
    """Assert that judge scores meet minimum thresholds."""
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


__all__ = ["ScoreResult", "ScoringDimension", "assert_score"]
