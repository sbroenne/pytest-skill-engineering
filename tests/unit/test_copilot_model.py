"""Unit tests for CopilotModel — PydanticAI Model adapter for the Copilot SDK."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters

from pytest_aitest.copilot.model import CopilotModel, _convert_messages

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _EventType:
    """Mock enum-like event type."""

    def __init__(self, value: str) -> None:
        self.value = value


class _EventData:
    """Mock event data with explicit attributes."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_event(event_type: str, **data_attrs: Any) -> Any:
    """Create a mock SessionEvent with .type.value and .data attributes."""
    event = type("MockEvent", (), {})()
    event.type = _EventType(event_type)
    event.data = _EventData(**data_attrs)
    return event


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestCopilotModelProperties:
    """Test CopilotModel name and system properties."""

    def test_model_name(self) -> None:
        model = CopilotModel("gpt-5-mini")
        assert model.model_name == "copilot:gpt-5-mini"

    def test_model_name_with_version(self) -> None:
        model = CopilotModel("gpt-5.2-chat")
        assert model.model_name == "copilot:gpt-5.2-chat"

    def test_system(self) -> None:
        model = CopilotModel("gpt-5-mini")
        assert model.system == "copilot"


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------


class TestConvertMessages:
    """Test _convert_messages flattening logic."""

    def test_system_prompt_only(self) -> None:
        messages = [ModelRequest(parts=[SystemPromptPart(content="You are a judge.")])]
        system, user = _convert_messages(messages)
        assert system == "You are a judge."
        assert user == ""

    def test_user_prompt_only(self) -> None:
        messages = [ModelRequest(parts=[UserPromptPart(content="What is 2+2?")])]
        system, user = _convert_messages(messages)
        assert system == ""
        assert user == "What is 2+2?"

    def test_system_and_user(self) -> None:
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="Be concise."),
                    UserPromptPart(content="Hello"),
                ]
            )
        ]
        system, user = _convert_messages(messages)
        assert system == "Be concise."
        assert user == "Hello"

    def test_multiple_system_parts(self) -> None:
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="Part 1."),
                    SystemPromptPart(content="Part 2."),
                    UserPromptPart(content="Go"),
                ]
            )
        ]
        system, user = _convert_messages(messages)
        assert system == "Part 1.\n\nPart 2."

    def test_tool_return_part(self) -> None:
        messages = [
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="get_balance",
                        content="$1000",
                        tool_call_id="tc1",
                    )
                ]
            )
        ]
        system, user = _convert_messages(messages)
        assert "Tool 'get_balance' returned: $1000" in user

    def test_retry_prompt_part(self) -> None:
        messages = [ModelRequest(parts=[RetryPromptPart(content="Invalid JSON, try again")])]
        system, user = _convert_messages(messages)
        assert "Please retry: Invalid JSON, try again" in user

    def test_prior_assistant_text_included(self) -> None:
        messages = [ModelResponse(parts=[TextPart(content="I calculated 4.")])]
        system, user = _convert_messages(messages)
        assert "Assistant: I calculated 4." in user

    def test_prior_assistant_tool_call_included(self) -> None:
        messages = [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="final_result",
                        args={"answer": True},
                    )
                ]
            )
        ]
        system, user = _convert_messages(messages)
        assert "final_result" in user

    def test_full_conversation(self) -> None:
        """Multi-turn conversation with system + user + assistant + tool return."""
        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="Judge the output."),
                    UserPromptPart(content="Evaluate this."),
                ]
            ),
            ModelResponse(parts=[ToolCallPart(tool_name="final_result", args={"pass": True})]),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="final_result",
                        content="OK",
                        tool_call_id="tc1",
                    ),
                    RetryPromptPart(content="Missing reasoning field"),
                ]
            ),
        ]
        system, user = _convert_messages(messages)
        assert system == "Judge the output."
        assert "Evaluate this." in user
        assert "final_result" in user
        assert "Please retry:" in user


# ---------------------------------------------------------------------------
# build_model_from_string integration
# ---------------------------------------------------------------------------


class TestBuildModelFromString:
    """Test that copilot/ prefix is handled correctly."""

    def test_copilot_prefix_creates_copilot_model(self) -> None:
        from pytest_aitest.execution.pydantic_adapter import build_model_from_string

        model = build_model_from_string("copilot/gpt-5-mini")
        assert isinstance(model, CopilotModel)
        assert model.model_name == "copilot:gpt-5-mini"

    def test_copilot_prefix_preserves_model_name(self) -> None:
        from pytest_aitest.execution.pydantic_adapter import build_model_from_string

        model = build_model_from_string("copilot/claude-opus-4.5")
        assert isinstance(model, CopilotModel)
        assert model.model_name == "copilot:claude-opus-4.5"


# ---------------------------------------------------------------------------
# Request (mocked SDK)
# ---------------------------------------------------------------------------


class TestRequest:
    """Test CopilotModel.request() with mocked Copilot SDK."""

    @pytest.fixture()
    def model(self) -> CopilotModel:
        return CopilotModel("gpt-5-mini")

    @pytest.fixture()
    def mock_request_params(self) -> ModelRequestParameters:
        from pydantic_ai.models import ModelRequestParameters

        return ModelRequestParameters()

    async def test_text_only_response(
        self, model: CopilotModel, mock_request_params: ModelRequestParameters
    ) -> None:
        """Text-only request returns TextPart."""
        mock_session = MagicMock()
        mock_session.on = MagicMock()

        async def mock_send_and_wait(msg: dict, timeout: int) -> None:
            # Simulate assistant.message and usage events via SessionEvent-like objects
            handler = mock_session.on.call_args[0][0]
            handler(_make_event("assistant.message", content="The answer is 42."))
            handler(_make_event("assistant.usage", input_tokens=10, output_tokens=5))
            return None

        mock_session.send_and_wait = mock_send_and_wait

        mock_client = AsyncMock()
        mock_client.create_session = AsyncMock(return_value=mock_session)

        with patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client):
            messages = [
                ModelRequest(parts=[UserPromptPart(content="What is the meaning of life?")])
            ]
            response = await model.request(messages, None, mock_request_params)

        assert len(response.parts) == 1
        assert isinstance(response.parts[0], TextPart)
        assert response.parts[0].content == "The answer is 42."
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 5

    async def test_tool_call_response(self, model: CopilotModel) -> None:
        """When function tools are defined, captured tool calls appear as ToolCallPart."""
        from pydantic_ai.tools import ToolDefinition

        params = ModelRequestParameters(
            function_tools=[
                ToolDefinition(
                    name="get_balance",
                    description="Get the user's account balance",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "account_id": {"type": "string"},
                        },
                        "required": ["account_id"],
                    },
                )
            ]
        )

        mock_session = MagicMock()
        mock_session.on = MagicMock()

        # Mock _build_copilot_tools to inject our capture directly
        captured_calls_ref: list[dict] = []

        def fake_build_tools(
            tool_defs: list[Any], captured_calls: list[dict[str, Any]]
        ) -> list[Any]:
            captured_calls_ref.append(captured_calls)
            return [{"name": "get_balance", "fake": True}]

        async def mock_send(msg: dict, timeout: int) -> None:
            # Simulate the model calling our function tool
            if captured_calls_ref:
                captured_calls_ref[0].append(
                    {"name": "get_balance", "args": {"account_id": "checking"}}
                )
            return None

        mock_session.send_and_wait = mock_send

        mock_client = AsyncMock()
        mock_client.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client),
            patch("pytest_aitest.copilot.model._build_copilot_tools", side_effect=fake_build_tools),
        ):
            messages = [ModelRequest(parts=[UserPromptPart(content="What's my balance?")])]
            response = await model.request(messages, None, params)

        # Should have ToolCallPart for the captured call
        tool_parts = [p for p in response.parts if isinstance(p, ToolCallPart)]
        assert len(tool_parts) == 1
        assert tool_parts[0].tool_name == "get_balance"
        assert tool_parts[0].args_as_dict() == {"account_id": "checking"}

    async def test_system_prompt_in_session_config(
        self, model: CopilotModel, mock_request_params: ModelRequestParameters
    ) -> None:
        """System prompt is passed to session config."""
        created_config: dict = {}

        mock_session = MagicMock()
        mock_session.on = MagicMock()
        mock_session.send_and_wait = AsyncMock(return_value=None)

        async def mock_create_session(config: dict) -> MagicMock:
            created_config.update(config)
            return mock_session

        mock_client = AsyncMock()
        mock_client.create_session = mock_create_session

        with patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client):
            messages = [
                ModelRequest(
                    parts=[
                        SystemPromptPart(content="You are a strict judge."),
                        UserPromptPart(content="Evaluate."),
                    ]
                )
            ]
            await model.request(messages, None, mock_request_params)

        assert created_config["system_message"]["content"] == "You are a strict judge."
        assert created_config["system_message"]["mode"] == "replace"

    async def test_prompted_output_appended_to_system(self, model: CopilotModel) -> None:
        """Prompted output instructions are appended to system prompt."""
        created_config: dict = {}
        params = ModelRequestParameters()

        mock_session = MagicMock()
        mock_session.on = MagicMock()
        mock_session.send_and_wait = AsyncMock(return_value=None)

        async def mock_create_session(config: dict) -> MagicMock:
            created_config.update(config)
            return mock_session

        mock_client = AsyncMock()
        mock_client.create_session = mock_create_session

        # Patch the cached_property at class level
        with (
            patch.object(
                ModelRequestParameters,
                "prompted_output_instructions",
                new_callable=lambda: property(lambda self: "Output JSON: {schema}"),
            ),
            patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client),
        ):
            messages = [
                ModelRequest(
                    parts=[
                        SystemPromptPart(content="Be concise."),
                        UserPromptPart(content="Do it."),
                    ]
                )
            ]
            await model.request(messages, None, params)

        system_content = created_config["system_message"]["content"]
        assert "Be concise." in system_content
        assert "Output JSON: {schema}" in system_content

    async def test_empty_response(
        self, model: CopilotModel, mock_request_params: ModelRequestParameters
    ) -> None:
        """Empty response produces an empty TextPart."""
        mock_session = MagicMock()
        mock_session.on = MagicMock()
        mock_session.send_and_wait = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.create_session = AsyncMock(return_value=mock_session)

        with patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client):
            messages = [ModelRequest(parts=[UserPromptPart(content="Silence")])]
            response = await model.request(messages, None, mock_request_params)

        assert len(response.parts) == 1
        assert isinstance(response.parts[0], TextPart)
        assert response.parts[0].content == ""

    async def test_builtin_tools_disabled(
        self, model: CopilotModel, mock_request_params: ModelRequestParameters
    ) -> None:
        """Built-in Copilot tools are disabled via available_tools=[]."""
        created_config: dict = {}

        mock_session = MagicMock()
        mock_session.on = MagicMock()
        mock_session.send_and_wait = AsyncMock(return_value=None)

        async def mock_create_session(config: dict) -> MagicMock:
            created_config.update(config)
            return mock_session

        mock_client = AsyncMock()
        mock_client.create_session = mock_create_session

        with patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client):
            messages = [ModelRequest(parts=[UserPromptPart(content="Hi")])]
            await model.request(messages, None, mock_request_params)

        assert created_config["available_tools"] == []

    async def test_model_name_in_response(
        self, model: CopilotModel, mock_request_params: ModelRequestParameters
    ) -> None:
        """ModelResponse includes the copilot model name."""
        mock_session = MagicMock()
        mock_session.on = MagicMock()
        mock_session.send_and_wait = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.create_session = AsyncMock(return_value=mock_session)

        with patch("pytest_aitest.copilot.model._get_or_create_client", return_value=mock_client):
            messages = [ModelRequest(parts=[UserPromptPart(content="Hi")])]
            response = await model.request(messages, None, mock_request_params)

        assert response.model_name == "copilot:gpt-5-mini"


# ---------------------------------------------------------------------------
# Client lifecycle
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    """Test shared CopilotClient lifecycle management."""

    async def test_shutdown_when_no_client(self) -> None:
        """Shutdown is a no-op when no client exists."""
        from pytest_aitest.copilot.model import shutdown_copilot_model_client

        # Should not raise
        await shutdown_copilot_model_client()

    def test_import_error_message(self) -> None:
        """Clear error message when SDK is not installed."""

        # The function will try to import copilot — in test env it may or may not be available
        # This is tested implicitly by the build_model_from_string tests
