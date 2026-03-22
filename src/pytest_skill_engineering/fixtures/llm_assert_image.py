"""LLM-powered image assertion fixture.

Provides the ``llm_assert_image`` fixture for evaluating images against
plain-English criteria using a vision-capable LLM judge via Copilot SDK.

NOTE: Image support in Copilot SDK is currently limited. This implementation
will raise NotImplementedError until vision capabilities are confirmed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pytest_skill_engineering.fixtures.llm_assert import AssertionResult


class LLMAssertImage:
    """Callable that evaluates an image against criteria using a vision LLM judge.

    NOTE: The Copilot SDK does not currently expose a clear API for sending
    images in messages. This fixture is a placeholder that raises
    NotImplementedError until vision support is confirmed.

    Example::

        async def test_dashboard(eval_run, agent, llm_assert_image):
            result = await eval_run(agent, "Create a dashboard")
            screenshots = result.tool_images_for("screenshot")
            assert llm_assert_image(
                screenshots[-1],
                "Shows 4 charts with no overlaps"
            )
    """

    def __init__(self, model: str) -> None:
        self._model = model

    def __call__(
        self,
        image: bytes | Any,
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

        Raises:
            NotImplementedError: Until Copilot SDK vision support is confirmed.
        """
        msg = (
            "Image assertions are not yet supported with the Copilot SDK. "
            "The Copilot SDK does not currently expose a documented API for "
            "sending images in session messages. This feature will be "
            "implemented once vision capabilities are confirmed in the SDK."
        )
        raise NotImplementedError(msg)


@pytest.fixture
def llm_assert_image(request: pytest.FixtureRequest) -> LLMAssertImage:
    """Fixture providing LLM-powered image assertions with a vision model.

    The vision model is resolved in this order:
    1. ``--llm-vision-model`` if explicitly set
    2. ``--llm-model`` (same model for text and image assertions)
    3. ``--aitest-summary-model``
    4. ``copilot/gpt-5-mini`` as final fallback

    NOTE: This fixture currently raises NotImplementedError when called,
    as the Copilot SDK does not yet support image inputs in a documented way.

    Example::

        async def test_chart(eval_run, agent, llm_assert_image):
            result = await eval_run(agent, "Create a bar chart")
            screenshots = result.tool_images_for("screenshot")
            assert llm_assert_image(screenshots[-1], "shows a bar chart")
    """
    _LLM_MODEL_DEFAULT = "copilot/gpt-5-mini"  # noqa: N806

    # Try vision-specific model first
    vision_model_str: str | None = request.config.getoption("--llm-vision-model", default=None)

    if vision_model_str:
        model_str = vision_model_str
    else:
        # Fall back to llm-model → summary model → default
        model_str = request.config.getoption("--llm-model")
        if model_str == "openai/gpt-5-mini":  # Old default
            model_str = _LLM_MODEL_DEFAULT
        if model_str == _LLM_MODEL_DEFAULT:
            summary_model = request.config.getoption("--aitest-summary-model", default=None)
            if summary_model:
                model_str = summary_model

    return LLMAssertImage(model=model_str)
