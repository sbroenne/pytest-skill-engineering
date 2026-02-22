"""Tests for multimodal tool result extraction in pydantic_adapter."""

from __future__ import annotations

from pytest_skill_engineering.execution.pydantic_adapter import (
    _extract_tool_result,
    _process_tool_content,
)


class TestProcessToolContent:
    """Tests for _process_tool_content with various content types."""

    def test_string_content(self) -> None:
        """Plain string content is returned as text."""
        result = _process_tool_content("hello world")
        assert result.text == "hello world"
        assert result.image_content is None
        assert result.image_media_type is None

    def test_dict_content(self) -> None:
        """Dict content is stringified."""
        result = _process_tool_content({"key": "value"})
        assert result.text == "{'key': 'value'}"
        assert result.image_content is None

    def test_none_content(self) -> None:
        """None content is stringified."""
        result = _process_tool_content(None)
        assert result.text == "None"
        assert result.image_content is None

    def test_binary_content_image(self) -> None:
        """BinaryContent with image data extracts bytes and media type."""
        from pydantic_ai.messages import BinaryContent

        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        content = BinaryContent(data=image_bytes, media_type="image/png")

        result = _process_tool_content(content)
        assert result.image_content == image_bytes
        assert result.image_media_type == "image/png"
        assert "[image/png, 108 bytes]" in result.text

    def test_binary_image_subclass(self) -> None:
        """BinaryImage (subclass of BinaryContent) is handled correctly."""
        from pydantic_ai.messages import BinaryImage

        image_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        content = BinaryImage(data=image_bytes, media_type="image/png")

        result = _process_tool_content(content)
        assert result.image_content == image_bytes
        assert result.image_media_type == "image/png"
        assert "58 bytes" in result.text

    def test_sequence_with_text_only(self) -> None:
        """List of strings is joined."""
        result = _process_tool_content(["line 1", "line 2"])
        assert "line 1" in result.text
        assert "line 2" in result.text
        assert result.image_content is None

    def test_sequence_with_image(self) -> None:
        """List containing BinaryContent extracts the image."""
        from pydantic_ai.messages import BinaryContent

        image_bytes = b"\x89PNG" + b"\x00" * 20
        content = [
            BinaryContent(data=image_bytes, media_type="image/png"),
            "Screenshot captured successfully",
        ]

        result = _process_tool_content(content)
        assert result.image_content == image_bytes
        assert result.image_media_type == "image/png"
        assert "Screenshot captured successfully" in result.text

    def test_sequence_first_image_wins(self) -> None:
        """When sequence has multiple images, first one is kept."""
        from pydantic_ai.messages import BinaryContent

        img1 = b"\x89PNG_1"
        img2 = b"\x89PNG_2"
        content = [
            BinaryContent(data=img1, media_type="image/png"),
            BinaryContent(data=img2, media_type="image/jpeg"),
        ]

        result = _process_tool_content(content)
        assert result.image_content == img1
        assert result.image_media_type == "image/png"


class TestExtractToolResult:
    """Tests for _extract_tool_result with PydanticAI message history."""

    def test_no_tool_call_id(self) -> None:
        """Returns empty result when tool_call_id is None."""
        result = _extract_tool_result([], None)
        assert result.text is None
        assert result.image_content is None

    def test_text_result(self) -> None:
        """Finds text tool result in message history."""
        from pydantic_ai.messages import ModelRequest, ToolReturnPart

        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="my_tool",
                        content='{"success": true}',
                        tool_call_id="call_123",
                    )
                ]
            )
        ]

        result = _extract_tool_result(messages, "call_123")
        assert result.text == '{"success": true}'
        assert result.image_content is None

    def test_image_result(self) -> None:
        """Finds image tool result in message history."""
        from pydantic_ai.messages import BinaryContent, ModelRequest, ToolReturnPart

        image_bytes = b"\x89PNG" + b"\x00" * 100
        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="screenshot",
                        content=BinaryContent(data=image_bytes, media_type="image/png"),
                        tool_call_id="call_456",
                    )
                ]
            )
        ]

        result = _extract_tool_result(messages, "call_456")
        assert result.image_content == image_bytes
        assert result.image_media_type == "image/png"
        assert "image/png" in result.text

    def test_missing_tool_call_id(self) -> None:
        """Returns empty result when tool_call_id not found."""
        from pydantic_ai.messages import ModelRequest, ToolReturnPart

        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="tool",
                        content="result",
                        tool_call_id="other_id",
                    )
                ]
            )
        ]

        result = _extract_tool_result(messages, "nonexistent")
        assert result.text is None

    def test_companion_image_in_user_prompt(self) -> None:
        """Extracts image from companion UserPromptPart when PydanticAI moves binary content.

        PydanticAI replaces BinaryImage in ToolReturnPart.content with
        "See file <id>" and stores the actual image in a companion
        UserPromptPart in the same ModelRequest.
        """
        from pydantic_ai.messages import (
            BinaryImage,
            ModelRequest,
            ToolReturnPart,
            UserPromptPart,
        )

        image_bytes = b"\x89PNG" + b"\x00" * 100
        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="screenshot",
                        content=["See file abc123", "Screenshot: A1:F20 (800x600px)"],
                        tool_call_id="call_img",
                    ),
                    UserPromptPart(
                        content=[
                            "This is file abc123:",
                            BinaryImage(data=image_bytes, media_type="image/png"),
                        ]
                    ),
                ]
            )
        ]

        result = _extract_tool_result(messages, "call_img")
        assert result.image_content == image_bytes
        assert result.image_media_type == "image/png"
        # Text should contain the original "See file" content
        assert "See file" in (result.text or "")

    def test_companion_image_no_user_prompt(self) -> None:
        """Returns no image when ToolReturnPart has 'See file' but no companion UserPromptPart."""
        from pydantic_ai.messages import ModelRequest, ToolReturnPart

        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="screenshot",
                        content="See file abc123",
                        tool_call_id="call_noimg",
                    ),
                ]
            )
        ]

        result = _extract_tool_result(messages, "call_noimg")
        assert result.text == "See file abc123"
        assert result.image_content is None
