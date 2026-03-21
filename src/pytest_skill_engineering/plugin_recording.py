"""Recording wrappers for LLM assertion and scoring fixtures.

These classes wrap the raw llm_assert / llm_assert_image / llm_score fixtures
so that every assertion result is captured for inclusion in test reports.
"""

from __future__ import annotations

from typing import Any


class RecordingLLMAssert:
    """Wrapper that records LLM assertions for report rendering."""

    def __init__(self, inner: Any, store: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def __call__(self, content: str, criterion: str) -> Any:
        result = self._inner(content, criterion)
        self._store.append(
            {
                "type": "llm",
                "passed": bool(result),
                "message": result.criterion,
                "details": result.reasoning,
            }
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class RecordingLLMAssertImage:
    """Wrapper that records LLM image assertions for report rendering."""

    def __init__(self, inner: Any, store: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def __call__(self, image: Any, criterion: str, **kwargs: Any) -> Any:
        result = self._inner(image, criterion, **kwargs)
        self._store.append(
            {
                "type": "llm_image",
                "passed": bool(result),
                "message": result.criterion,
                "details": result.reasoning,
            }
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class RecordingLLMScore:
    """Wrapper that records multi-dimension LLM scores for report rendering."""

    def __init__(self, inner: Any, store: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def _record(self, result: Any, rubric: Any) -> Any:
        """Store score data including per-dimension detail."""
        dimensions = []
        for dim in rubric:
            dimensions.append(
                {
                    "name": dim.name,
                    "score": result.scores.get(dim.name, 0),
                    "max_score": dim.max_score,
                    "weight": dim.weight,
                }
            )
        self._store.append(
            {
                "type": "llm_score",
                "passed": True,  # scoring always succeeds; thresholds checked via assert_score
                "message": f"{result.total}/{result.max_total} ({result.weighted_score:.0%})",
                "details": result.reasoning,
                "dimensions": dimensions,
                "total": result.total,
                "max_total": result.max_total,
                "weighted_score": result.weighted_score,
            }
        )
        return result

    def __call__(self, content: str, rubric: Any, **kwargs: Any) -> Any:
        result = self._inner(content, rubric, **kwargs)
        return self._record(result, rubric)

    async def async_score(self, content: str, rubric: Any, **kwargs: Any) -> Any:
        result = await self._inner.async_score(content, rubric, **kwargs)
        return self._record(result, rubric)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
