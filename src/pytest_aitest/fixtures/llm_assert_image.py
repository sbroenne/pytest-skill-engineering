"""LLM-powered image assertion fixture.

Provides the ``llm_assert_image`` fixture for evaluating images against
plain-English criteria using a vision-capable LLM judge via pydantic-evals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from pytest_aitest.fixtures.llm_assert import AssertionResult

if TYPE_CHECKING:
    from pytest_aitest.core.result import ImageContent


class LLMAssertImage:
    """Callable that evaluates an image against criteria using a vision LLM judge.

    Uses ``pydantic_evals.evaluators.llm_as_a_judge.judge_output()`` which
    natively supports multimodal content including images.

    Example::

        async def test_dashboard(aitest_run, agent, llm_assert_image):
            result = await aitest_run(agent, "Create a dashboard")
            screenshots = result.tool_images_for("screenshot")
            assert llm_assert_image(
                screenshots[-1],
                "Shows 4 charts with no overlaps"
            )
    """

    def __init__(self, model: Any) -> None:
        self._model = model

    def __call__(
        self,
        image: bytes | ImageContent,
        criterion: str,
        *,
        media_type: str = "image/png",
    ) -> AssertionResult:
        """Evaluate if an image meets the given criterion.

        Args:
            image: Image bytes, or an ImageContent object from tool_images_for().
            criterion: Plain English criterion (e.g., "shows 4 charts with no overlaps").
            media_type: MIME type when image is raw bytes (default: image/png).

        Returns:
            AssertionResult that is truthy if criterion is met.
        """
        import asyncio
        import concurrent.futures

        from pydantic_ai.messages import BinaryContent
        from pydantic_evals.evaluators.llm_as_a_judge import judge_output

        # Normalize to BinaryContent
        if isinstance(image, bytes):
            binary = BinaryContent(data=image, media_type=media_type)
        elif hasattr(image, "data") and hasattr(image, "media_type"):
            # ImageContent dataclass
            binary = BinaryContent(data=image.data, media_type=image.media_type)
        else:
            msg = f"Expected bytes or ImageContent, got {type(image).__name__}"
            raise TypeError(msg)

        async def _judge() -> Any:
            return await judge_output(
                output=[binary],
                rubric=criterion,
                model=self._model,
            )

        # judge_output is async, but llm_assert_image is called synchronously
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            grading = pool.submit(asyncio.run, _judge()).result()

        return AssertionResult(
            passed=grading.pass_,
            criterion=criterion,
            reasoning=grading.reason,
            content_preview=f"[image, {len(binary.data)} bytes]",
        )


@pytest.fixture
def llm_assert_image(request: pytest.FixtureRequest) -> LLMAssertImage:
    """Fixture providing LLM-powered image assertions with a vision model.

    The vision model is resolved in this order:
    1. ``--llm-vision-model`` if explicitly set
    2. ``--llm-model`` (same model for text and image assertions)
    3. ``--aitest-summary-model``
    4. ``openai/gpt-5-mini`` as final fallback

    Example::

        async def test_chart(aitest_run, agent, llm_assert_image):
            result = await aitest_run(agent, "Create a bar chart")
            screenshots = result.tool_images_for("screenshot")
            assert llm_assert_image(screenshots[-1], "shows a bar chart")
    """
    from pytest_aitest.fixtures.llm_assert import _build_judge_model

    _LLM_MODEL_DEFAULT = "openai/gpt-5-mini"  # noqa: N806

    # Try vision-specific model first
    vision_model_str: str | None = request.config.getoption("--llm-vision-model", default=None)

    if vision_model_str:
        model = _build_judge_model(vision_model_str)
    else:
        # Fall back to llm-model → summary model → default
        model_str: str = request.config.getoption("--llm-model")
        if model_str == _LLM_MODEL_DEFAULT:
            summary_model = request.config.getoption("--aitest-summary-model", default=None)
            if summary_model:
                model_str = summary_model
        model = _build_judge_model(model_str)

    return LLMAssertImage(model=model)
