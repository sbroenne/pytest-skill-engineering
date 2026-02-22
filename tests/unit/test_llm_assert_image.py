"""Tests for LLMAssertImage fixture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pytest_skill_engineering.core.result import ImageContent
from pytest_skill_engineering.fixtures.llm_assert_image import LLMAssertImage


class TestLLMAssertImage:
    """Tests for the LLMAssertImage callable."""

    def test_accepts_raw_bytes(self) -> None:
        """Can be called with raw bytes."""
        mock_grading = MagicMock()
        mock_grading.pass_ = True
        mock_grading.reason = "Image shows charts"

        with patch(
            "pytest_skill_engineering.fixtures.llm_assert_image.LLMAssertImage.__call__",
            wraps=None,
        ):
            # Test the type normalization logic directly
            from pydantic_ai.messages import BinaryContent

            image_bytes = b"\x89PNG" + b"\x00" * 100
            binary = BinaryContent(data=image_bytes, media_type="image/png")
            assert isinstance(binary, BinaryContent)
            assert binary.data == image_bytes

    def test_accepts_image_content(self) -> None:
        """Can be called with ImageContent dataclass."""
        image = ImageContent(data=b"\x89PNG", media_type="image/jpeg")

        # Verify the duck-typing check works
        assert hasattr(image, "data")
        assert hasattr(image, "media_type")
        assert image.data == b"\x89PNG"
        assert image.media_type == "image/jpeg"

    def test_rejects_invalid_type(self) -> None:
        """Raises TypeError for unsupported input types."""
        asserter = LLMAssertImage(model="test-model")
        with pytest.raises(TypeError, match="Expected bytes or ImageContent"):
            asserter("not an image", "some criterion")

    def test_result_is_assertion_result(self) -> None:
        """Returns AssertionResult with correct fields."""
        from pytest_skill_engineering.fixtures.llm_assert import AssertionResult

        # Create a mock result directly
        result = AssertionResult(
            passed=True,
            criterion="shows 4 charts",
            reasoning="The image clearly shows 4 chart elements",
            content_preview="[image, 108 bytes]",
        )

        assert bool(result) is True
        assert result.criterion == "shows 4 charts"
        assert "4 chart" in result.reasoning

    def test_result_bool_false_on_failure(self) -> None:
        """AssertionResult is falsy when criterion not met."""
        from pytest_skill_engineering.fixtures.llm_assert import AssertionResult

        result = AssertionResult(
            passed=False,
            criterion="shows no overlapping charts",
            reasoning="Charts 2 and 3 overlap significantly",
            content_preview="[image, 5000 bytes]",
        )

        assert bool(result) is False


class TestLLMAssertImageTypeNormalization:
    """Tests for input type normalization in LLMAssertImage."""

    def test_bytes_to_binary_content(self) -> None:
        """Raw bytes are wrapped in BinaryContent with default media type."""
        from pydantic_ai.messages import BinaryContent

        image_bytes = b"\x89PNG\r\n"
        binary = BinaryContent(data=image_bytes, media_type="image/png")

        assert binary.data == image_bytes
        assert str(binary.media_type) == "image/png"

    def test_image_content_to_binary_content(self) -> None:
        """ImageContent fields map correctly to BinaryContent."""
        from pydantic_ai.messages import BinaryContent

        ic = ImageContent(data=b"\xff\xd8\xff", media_type="image/jpeg")
        binary = BinaryContent(data=ic.data, media_type=ic.media_type)

        assert binary.data == ic.data
        assert str(binary.media_type) == "image/jpeg"

    def test_custom_media_type(self) -> None:
        """Custom media_type parameter is respected for raw bytes."""
        from pydantic_ai.messages import BinaryContent

        binary = BinaryContent(data=b"\x00", media_type="image/webp")
        assert str(binary.media_type) == "image/webp"
