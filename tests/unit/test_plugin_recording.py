"""Unit tests for plugin recording wrappers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pytest_skill_engineering.plugin_recording import (
    RecordingLLMAssert,
    RecordingLLMAssertImage,
    RecordingLLMScore,
)


@dataclass(slots=True)
class FakeAssertionResult:
    """Minimal assertion result object with explicit truthiness."""

    criterion: str
    reasoning: str
    truthy: bool

    def __bool__(self) -> bool:
        return self.truthy


@dataclass(slots=True)
class FakeScoreDimension:
    """Minimal rubric dimension."""

    name: str
    max_score: int
    weight: float


@dataclass(slots=True)
class FakeScoreResult:
    """Minimal score result object."""

    scores: dict[str, int]
    total: int
    max_total: int
    weighted_score: float
    reasoning: str


@dataclass(slots=True)
class FakeLLMAssertInner:
    """Concrete fake for assertion wrapper tests."""

    result: FakeAssertionResult
    calls: list[tuple[str, str]] = field(default_factory=list)
    some_attribute: str = "inner-assert-attribute"

    def __call__(self, content: str, criterion: str) -> FakeAssertionResult:
        self.calls.append((content, criterion))
        return self.result


@dataclass(slots=True)
class FakeLLMAssertImageInner:
    """Concrete fake for image assertion wrapper tests."""

    result: FakeAssertionResult
    calls: list[tuple[Any, str, dict[str, Any]]] = field(default_factory=list)
    some_attribute: str = "inner-image-attribute"

    def __call__(self, image: Any, criterion: str, **kwargs: Any) -> FakeAssertionResult:
        self.calls.append((image, criterion, kwargs))
        return self.result


@dataclass(slots=True)
class FakeLLMScoreInner:
    """Concrete fake for score wrapper tests."""

    sync_result: FakeScoreResult
    async_result: FakeScoreResult
    sync_calls: list[tuple[str, list[FakeScoreDimension], dict[str, Any]]] = field(
        default_factory=list
    )
    async_calls: list[tuple[str, list[FakeScoreDimension], dict[str, Any]]] = field(
        default_factory=list
    )
    some_attribute: str = "inner-score-attribute"

    def __call__(
        self, content: str, rubric: list[FakeScoreDimension], **kwargs: Any
    ) -> FakeScoreResult:
        self.sync_calls.append((content, rubric, kwargs))
        return self.sync_result

    async def async_score(
        self, content: str, rubric: list[FakeScoreDimension], **kwargs: Any
    ) -> FakeScoreResult:
        self.async_calls.append((content, rubric, kwargs))
        return self.async_result


class TestRecordingLLMAssert:
    """Tests for RecordingLLMAssert."""

    def test_call_returns_inner_result_and_records_truthy_result(self) -> None:
        result = FakeAssertionResult(
            criterion="contains the answer",
            reasoning="The answer is present.",
            truthy=True,
        )
        inner = FakeLLMAssertInner(result=result)
        store: list[dict[str, Any]] = []
        wrapped = RecordingLLMAssert(inner, store)

        returned = wrapped("response content", "contains the answer")

        assert returned is result
        assert inner.calls == [("response content", "contains the answer")]
        assert store == [
            {
                "type": "llm",
                "passed": True,
                "message": "contains the answer",
                "details": "The answer is present.",
            }
        ]

    def test_call_records_falsy_result_using_bool(self) -> None:
        result = FakeAssertionResult(
            criterion="mentions the balance",
            reasoning="The balance was not mentioned.",
            truthy=False,
        )
        store: list[dict[str, Any]] = []
        wrapped = RecordingLLMAssert(FakeLLMAssertInner(result=result), store)

        returned = wrapped("No balance here", "mentions the balance")

        assert returned is result
        assert store == [
            {
                "type": "llm",
                "passed": False,
                "message": "mentions the balance",
                "details": "The balance was not mentioned.",
            }
        ]

    def test_getattr_delegates_to_inner(self) -> None:
        wrapped = RecordingLLMAssert(
            FakeLLMAssertInner(result=FakeAssertionResult("criterion", "reasoning", truthy=True)),
            [],
        )

        assert wrapped.some_attribute == "inner-assert-attribute"


class TestRecordingLLMAssertImage:
    """Tests for RecordingLLMAssertImage."""

    def test_call_passes_kwargs_and_records_image_assertion(self) -> None:
        result = FakeAssertionResult(
            criterion="shows a chart",
            reasoning="A chart is visible in the image.",
            truthy=True,
        )
        inner = FakeLLMAssertImageInner(result=result)
        store: list[dict[str, Any]] = []
        wrapped = RecordingLLMAssertImage(inner, store)
        image = object()

        returned = wrapped(image, "shows a chart", threshold=0.9, mode="strict")

        assert returned is result
        assert inner.calls == [(image, "shows a chart", {"threshold": 0.9, "mode": "strict"})]
        assert store == [
            {
                "type": "llm_image",
                "passed": True,
                "message": "shows a chart",
                "details": "A chart is visible in the image.",
            }
        ]

    def test_getattr_delegates_to_inner(self) -> None:
        wrapped = RecordingLLMAssertImage(
            FakeLLMAssertImageInner(
                result=FakeAssertionResult("criterion", "reasoning", truthy=True)
            ),
            [],
        )

        assert wrapped.some_attribute == "inner-image-attribute"


class TestRecordingLLMScore:
    """Tests for RecordingLLMScore."""

    def test_call_records_dimensions_message_and_missing_scores(self) -> None:
        rubric = [
            FakeScoreDimension(name="accuracy", max_score=5, weight=0.7),
            FakeScoreDimension(name="clarity", max_score=3, weight=0.3),
        ]
        result = FakeScoreResult(
            scores={"accuracy": 1},
            total=1,
            max_total=8,
            weighted_score=0.755,
            reasoning="Low raw score, but weighted result is rounded for display.",
        )
        inner = FakeLLMScoreInner(sync_result=result, async_result=result)
        store: list[dict[str, Any]] = []
        wrapped = RecordingLLMScore(inner, store)

        returned = wrapped("draft answer", rubric, threshold=0.8)

        assert returned is result
        assert inner.sync_calls == [("draft answer", rubric, {"threshold": 0.8})]
        assert store == [
            {
                "type": "llm_score",
                "passed": True,
                "message": "1/8 (76%)",
                "details": "Low raw score, but weighted result is rounded for display.",
                "dimensions": [
                    {"name": "accuracy", "score": 1, "max_score": 5, "weight": 0.7},
                    {"name": "clarity", "score": 0, "max_score": 3, "weight": 0.3},
                ],
                "total": 1,
                "max_total": 8,
                "weighted_score": 0.755,
            }
        ]

    async def test_async_score_records_and_appends_to_existing_store(self) -> None:
        rubric = [FakeScoreDimension(name="completeness", max_score=4, weight=1.0)]
        sync_result = FakeScoreResult(
            scores={"completeness": 0},
            total=0,
            max_total=4,
            weighted_score=0.0,
            reasoning="Not used in this test.",
        )
        async_result = FakeScoreResult(
            scores={"completeness": 1},
            total=1,
            max_total=4,
            weighted_score=0.125,
            reasoning="Partial completion only.",
        )
        inner = FakeLLMScoreInner(sync_result=sync_result, async_result=async_result)
        store: list[dict[str, Any]] = [{"type": "existing"}]
        wrapped = RecordingLLMScore(inner, store)

        returned = await wrapped.async_score("partial answer", rubric, judge="fast")

        assert returned is async_result
        assert inner.async_calls == [("partial answer", rubric, {"judge": "fast"})]
        assert store == [
            {"type": "existing"},
            {
                "type": "llm_score",
                "passed": True,
                "message": "1/4 (12%)",
                "details": "Partial completion only.",
                "dimensions": [
                    {
                        "name": "completeness",
                        "score": 1,
                        "max_score": 4,
                        "weight": 1.0,
                    }
                ],
                "total": 1,
                "max_total": 4,
                "weighted_score": 0.125,
            },
        ]

    def test_getattr_delegates_to_inner(self) -> None:
        result = FakeScoreResult(
            scores={},
            total=0,
            max_total=1,
            weighted_score=0.0,
            reasoning="reasoning",
        )
        wrapped = RecordingLLMScore(
            FakeLLMScoreInner(sync_result=result, async_result=result),
            [],
        )

        assert wrapped.some_attribute == "inner-score-attribute"


class TestRecordingStoreBehavior:
    """Tests for shared store mutation behavior across wrappers."""

    def test_multiple_wrappers_append_to_same_store_in_place(self) -> None:
        store: list[dict[str, Any]] = []
        assert_wrapper = RecordingLLMAssert(
            FakeLLMAssertInner(
                result=FakeAssertionResult("criterion one", "reason one", truthy=True)
            ),
            store,
        )
        image_wrapper = RecordingLLMAssertImage(
            FakeLLMAssertImageInner(
                result=FakeAssertionResult("criterion two", "reason two", truthy=False)
            ),
            store,
        )
        score_result = FakeScoreResult(
            scores={"accuracy": 2},
            total=2,
            max_total=5,
            weighted_score=0.4,
            reasoning="Needs improvement.",
        )
        score_wrapper = RecordingLLMScore(
            FakeLLMScoreInner(sync_result=score_result, async_result=score_result),
            store,
        )

        assert_wrapper("content", "criterion one")
        image_wrapper(object(), "criterion two")
        score_wrapper("scored content", [FakeScoreDimension("accuracy", 5, 1.0)])

        assert len(store) == 3
        assert [entry["type"] for entry in store] == ["llm", "llm_image", "llm_score"]
