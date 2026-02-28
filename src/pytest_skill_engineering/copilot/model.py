"""CopilotModel — PydanticAI Model adapter for the GitHub Copilot SDK.

Routes LLM calls through the Copilot SDK, enabling users with
pytest-skill-engineering[copilot] to use Copilot-accessible models for judge,
summary, assertion, and optimizer calls without separate Azure/OpenAI setup.

Usage::

    --aitest-summary-model=copilot/gpt-5-mini
    --llm-model=copilot/gpt-5-mini
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.usage import RequestUsage

if TYPE_CHECKING:
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolDefinition

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton CopilotClient
# ---------------------------------------------------------------------------

_client: Any | None = None
_client_lock: asyncio.Lock | None = None
_client_lock_loop: asyncio.AbstractEventLoop | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def _get_lock() -> asyncio.Lock:
    """Get or create the client lock (lazy to avoid event loop issues at import)."""
    global _client_lock, _client_lock_loop
    current_loop = asyncio.get_running_loop()
    if _client_lock is None or _client_lock_loop is not current_loop:
        _client_lock = asyncio.Lock()
        _client_lock_loop = current_loop
    return _client_lock


async def _get_or_create_client() -> Any:
    """Get or create a shared CopilotClient singleton.

    The client is expensive to start (spawns a process), so we reuse it
    across all model calls in the same process.  If the event loop has
    changed (e.g. between pytest tests), recreates the client.
    """
    global _client, _client_loop

    async with _get_lock():
        current_loop = asyncio.get_running_loop()
        # If the loop changed, client is stale — reset under lock.
        if _client_loop is not None and _client_loop is not current_loop:
            _logger.debug("Event loop changed — resetting CopilotClient singleton")
            _client = None
            _client_loop = None

        if _client is not None:
            return _client

        try:
            from copilot import CopilotClient
        except ImportError as exc:
            msg = (
                "github-copilot-sdk is required for the copilot/ model provider. "
                "Install with: uv add pytest-skill-engineering[copilot]"
            )
            raise ImportError(msg) from exc

        options: dict[str, Any] = {
            "cwd": ".",
            "auto_start": True,
            "log_level": "warning",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            options["github_token"] = token

        from copilot.types import CopilotClientOptions

        _client = CopilotClient(options=CopilotClientOptions(**options))
        await asyncio.wait_for(_client.start(), timeout=60)
        _client_loop = current_loop
        _logger.info("Shared CopilotClient started for model provider")
        return _client


async def shutdown_copilot_model_client() -> None:
    """Shutdown the shared CopilotClient.

    Called from ``pytest_sessionfinish`` to clean up the background process.
    Acquires the client lock to avoid races with concurrent requests.
    """
    global _client, _client_loop
    async with _get_lock():
        if _client is None:
            return
        try:
            await _client.stop()
        except Exception:
            try:
                await _client.force_stop()
            except Exception:
                pass
        _client = None
        _client_loop = None
        _logger.info("Shared CopilotClient stopped")


# ---------------------------------------------------------------------------
# CopilotModel
# ---------------------------------------------------------------------------


class CopilotModel(Model):
    """PydanticAI Model backed by the GitHub Copilot SDK.

    Wraps the Copilot SDK session API to implement PydanticAI's Model protocol.
    Uses text-based (prompted) structured output because the Copilot SDK's
    built-in system prompt interferes with PydanticAI's tool-calling approach.
    """

    _model: str

    def __init__(self, model_name: str) -> None:
        from pydantic_ai.profiles import ModelProfile

        super().__init__(
            profile=ModelProfile(default_structured_output_mode="prompted"),
        )
        self._model = model_name

    @property
    def model_name(self) -> str:
        return f"copilot:{self._model}"

    @property
    def system(self) -> str:
        return "copilot"

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a request via the Copilot SDK."""
        model_settings, model_request_parameters = self.prepare_request(
            model_settings, model_request_parameters
        )

        client = await _get_or_create_client()

        # Build session config
        session_config: dict[str, Any] = {
            "model": self._model,
            "available_tools": [],  # Disable all built-in Copilot tools
        }

        # Extract system prompt and conversation from PydanticAI messages
        system_prompt, user_prompt = _convert_messages(messages)

        # Include prompted output instructions for text-based structured output
        if model_request_parameters.prompted_output_instructions:
            extra = model_request_parameters.prompted_output_instructions
            system_prompt = f"{system_prompt}\n\n{extra}" if system_prompt else extra

        if system_prompt:
            session_config["system_message"] = {
                "mode": "replace",
                "content": system_prompt,
            }

        # Convert PydanticAI tool definitions to Copilot tools
        tool_defs = [
            *model_request_parameters.function_tools,
            *model_request_parameters.output_tools,
        ]
        captured_tool_calls: list[dict[str, Any]] = []

        if tool_defs:
            session_config["tools"] = _build_copilot_tools(tool_defs, captured_tool_calls)

        # Collect response data from events
        text_parts: list[str] = []
        usage_data: dict[str, int] = {"input": 0, "output": 0}

        def event_handler(event: Any) -> None:
            _handle_event(event, text_parts, usage_data)

        # Auto-approve permissions for non-interactive model calls (judge, analysis)
        session_config["on_permission_request"] = _auto_approve_permissions

        # Create session and execute
        session = await asyncio.wait_for(
            client.create_session(session_config),
            timeout=30,
        )
        session.on(event_handler)

        result_event = await session.send_and_wait(
            {"prompt": user_prompt},
            timeout=120,
        )
        # send_and_wait may return a final event — only process if not
        # already captured by the on() handler (check for new text)
        if result_event is not None:
            pre_len = len(text_parts)
            _handle_event(result_event, text_parts, usage_data)
            # If this duplicated existing text, undo
            if len(text_parts) > pre_len and len(text_parts) >= 2:
                if text_parts[-1] == text_parts[-2]:
                    text_parts.pop()

        # Build ModelResponse
        response_parts: list[TextPart | ToolCallPart] = []

        for tc in captured_tool_calls:
            response_parts.append(ToolCallPart(tool_name=tc["name"], args=tc["args"]))

        # Only include text when there are no tool calls — PydanticAI
        # treats text as a fallback for structured output validation and
        # would fail if both text and tool calls are present.
        if not captured_tool_calls:
            full_text = "".join(text_parts)
            if full_text:
                response_parts.append(TextPart(content=full_text))

        if not response_parts:
            response_parts.append(TextPart(content=""))

        return ModelResponse(
            parts=response_parts,
            model_name=self.model_name,
            usage=RequestUsage(
                input_tokens=usage_data["input"],
                output_tokens=usage_data["output"],
            ),
        )


# ---------------------------------------------------------------------------
# Message conversion
# ---------------------------------------------------------------------------


def _convert_messages(messages: list[ModelMessage]) -> tuple[str, str]:
    """Convert PydanticAI messages to (system_prompt, user_prompt) strings.

    Flattens the structured PydanticAI message history into a single system
    prompt and conversation prompt suitable for the Copilot SDK's
    ``send_and_wait({"prompt": ...})`` API.
    """
    system_parts: list[str] = []
    conversation_parts: list[str] = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    system_parts.append(part.content)
                elif isinstance(part, UserPromptPart):
                    content = part.content if isinstance(part.content, str) else str(part.content)
                    conversation_parts.append(content)
                elif isinstance(part, ToolReturnPart):
                    conversation_parts.append(f"Tool '{part.tool_name}' returned: {part.content}")
                elif isinstance(part, RetryPromptPart):
                    content = part.content if isinstance(part.content, str) else str(part.content)
                    conversation_parts.append(f"Please retry: {content}")
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, TextPart):
                    conversation_parts.append(f"Assistant: {part.content}")
                elif isinstance(part, ToolCallPart):
                    conversation_parts.append(
                        f"Assistant called tool '{part.tool_name}' with args: "
                        f"{part.args_as_json_str()}"
                    )

    system_prompt = "\n\n".join(system_parts)
    user_prompt = "\n\n".join(conversation_parts) if conversation_parts else ""

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Tool conversion
# ---------------------------------------------------------------------------


def _build_copilot_tools(
    tool_defs: list[ToolDefinition],
    captured_calls: list[dict[str, Any]],
) -> list[Any]:
    """Convert PydanticAI ToolDefinitions to Copilot Tool objects.

    Each tool's handler captures the model's call arguments into
    ``captured_calls`` so they can be returned as ``ToolCallPart``
    in the ``ModelResponse``.
    """
    from copilot.types import Tool, ToolResult

    tools: list[Tool] = []
    for td in tool_defs:

        def _make_handler(tool_name: str) -> Any:
            async def _handler(invocation: Any) -> ToolResult:
                args = invocation.get("arguments") or {}
                captured_calls.append({"name": tool_name, "args": args})
                return ToolResult(
                    textResultForLlm=json.dumps({"status": "captured"}),
                    resultType="success",
                )

            return _handler

        tools.append(
            Tool(
                name=td.name,
                description=td.description or "",
                handler=_make_handler(td.name),
                parameters=td.parameters_json_schema,
            )
        )

    return tools


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------


def _handle_event(
    event: Any,
    text_parts: list[str],
    usage_data: dict[str, int],
) -> None:
    """Process a Copilot SDK SessionEvent, extracting text and usage data.

    SDK events have ``.type`` (enum with ``.value`` str) and ``.data``
    (object with typed attributes accessed via ``getattr``).

    Only captures ``assistant.message`` (complete messages) — NOT deltas —
    because the SDK fires both delta and complete events for the same content.
    """
    # Resolve event type string from enum or plain attribute
    event_type_raw = getattr(event, "type", None)
    if event_type_raw is None:
        return
    event_type = event_type_raw.value if hasattr(event_type_raw, "value") else str(event_type_raw)

    data = getattr(event, "data", None)

    if event_type == "assistant.message":
        content = getattr(data, "content", "") if data else ""
        if content:
            text_parts.append(str(content))
    elif event_type == "assistant.usage":
        if data:
            in_tokens = int(getattr(data, "input_tokens", 0) or 0)
            out_tokens = int(getattr(data, "output_tokens", 0) or 0)
            usage_data["input"] += in_tokens
            usage_data["output"] += out_tokens


# ---------------------------------------------------------------------------
# Permission handling
# ---------------------------------------------------------------------------


def _auto_approve_permissions(request: dict[str, Any], context: dict[str, str]) -> dict[str, str]:
    """Auto-approve all permission requests for non-interactive model calls.

    The CopilotModel is used for judge, analysis, and scoring — never for
    interactive sessions. Auto-approving is safe and required because
    the Copilot SDK mandates a permission handler.
    """
    return {"kind": "approved"}
