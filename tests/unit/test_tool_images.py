"""Tests for tool_images_for and ImageContent on EvalResult."""

from __future__ import annotations

from pytest_skill_engineering.core.result import EvalResult, ImageContent, ToolCall, Turn


class TestImageContent:
    """Tests for the ImageContent dataclass."""

    def test_repr(self) -> None:
        """ImageContent repr shows media type and size."""
        ic = ImageContent(data=b"\x89PNG" * 100, media_type="image/png")
        assert "image/png" in repr(ic)
        assert "400 bytes" in repr(ic)

    def test_fields(self) -> None:
        """ImageContent stores data and media_type."""
        data = b"\xff\xd8\xff"
        ic = ImageContent(data=data, media_type="image/jpeg")
        assert ic.data == data
        assert ic.media_type == "image/jpeg"


class TestToolImagesFor:
    """Tests for EvalResult.tool_images_for()."""

    def _make_result(self, tool_calls: list[ToolCall]) -> EvalResult:
        """Helper to create an EvalResult with tool calls."""
        turn = Turn(role="assistant", content="", tool_calls=tool_calls)
        return EvalResult(turns=[turn], success=True)

    def test_no_images(self) -> None:
        """Returns empty list when no tool calls have images."""
        tc = ToolCall(name="screenshot", arguments={}, result='{"success": true}')
        result = self._make_result([tc])
        assert result.tool_images_for("screenshot") == []

    def test_single_image(self) -> None:
        """Returns single ImageContent for tool with image."""
        image_data = b"\x89PNG" + b"\x00" * 50
        tc = ToolCall(
            name="screenshot",
            arguments={},
            result="[image/png, 54 bytes]",
            image_content=image_data,
            image_media_type="image/png",
        )
        result = self._make_result([tc])

        images = result.tool_images_for("screenshot")
        assert len(images) == 1
        assert images[0].data == image_data
        assert images[0].media_type == "image/png"

    def test_multiple_images(self) -> None:
        """Returns all images from multiple calls to same tool."""
        img1 = b"\x89PNG_1"
        img2 = b"\x89PNG_2"
        tc1 = ToolCall(
            name="screenshot",
            arguments={},
            image_content=img1,
            image_media_type="image/png",
        )
        tc2 = ToolCall(
            name="screenshot",
            arguments={},
            image_content=img2,
            image_media_type="image/png",
        )
        result = self._make_result([tc1, tc2])

        images = result.tool_images_for("screenshot")
        assert len(images) == 2
        assert images[0].data == img1
        assert images[1].data == img2

    def test_filters_by_tool_name(self) -> None:
        """Only returns images from the specified tool."""
        img = b"\x89PNG"
        tc1 = ToolCall(
            name="screenshot",
            arguments={},
            image_content=img,
            image_media_type="image/png",
        )
        tc2 = ToolCall(
            name="other_tool",
            arguments={},
            image_content=b"\xff\xd8",
            image_media_type="image/jpeg",
        )
        result = self._make_result([tc1, tc2])

        images = result.tool_images_for("screenshot")
        assert len(images) == 1
        assert images[0].data == img

    def test_skips_non_image_calls(self) -> None:
        """Mixed calls: only returns those with image_content."""
        img = b"\x89PNG"
        tc1 = ToolCall(name="screenshot", arguments={}, result="text only")
        tc2 = ToolCall(
            name="screenshot",
            arguments={},
            image_content=img,
            image_media_type="image/png",
        )
        result = self._make_result([tc1, tc2])

        images = result.tool_images_for("screenshot")
        assert len(images) == 1
        assert images[0].data == img

    def test_default_media_type(self) -> None:
        """Default media type is image/png when not specified."""
        tc = ToolCall(
            name="screenshot",
            arguments={},
            image_content=b"\x89PNG",
            image_media_type=None,  # Not set
        )
        result = self._make_result([tc])

        images = result.tool_images_for("screenshot")
        assert len(images) == 1
        assert images[0].media_type == "image/png"

    def test_across_multiple_turns(self) -> None:
        """Collects images from tool calls across multiple turns."""
        img1 = b"\x89PNG_1"
        img2 = b"\x89PNG_2"
        tc1 = ToolCall(
            name="screenshot",
            arguments={},
            image_content=img1,
            image_media_type="image/png",
        )
        tc2 = ToolCall(
            name="screenshot",
            arguments={},
            image_content=img2,
            image_media_type="image/png",
        )
        turn1 = Turn(role="assistant", content="", tool_calls=[tc1])
        turn2 = Turn(role="assistant", content="", tool_calls=[tc2])
        result = EvalResult(turns=[turn1, turn2], success=True)

        images = result.tool_images_for("screenshot")
        assert len(images) == 2
