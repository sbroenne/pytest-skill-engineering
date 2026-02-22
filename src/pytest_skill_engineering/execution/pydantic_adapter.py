"""Adapter between pytest-skill-engineering config types and PydanticAI types.

Converts our Agent/Provider/MCPServer config into PydanticAI Agent + toolsets,
and converts PydanticAI AgentRunResult back into our AgentResult for reporting.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP
from pydantic_ai.messages import (
    MULTI_MODAL_CONTENT_TYPES,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from pytest_skill_engineering.core.result import AgentResult, SkillInfo, ToolCall, ToolInfo, Turn

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult
    from pydantic_ai.mcp import MCPServer as PydanticMCPServer
    from pydantic_ai.models import Model
    from pydantic_ai.toolsets import AbstractToolset

    from pytest_skill_engineering.core.agent import Agent, MCPServer

_logger = logging.getLogger(__name__)


def build_pydantic_model(agent: Agent) -> Model:
    """Convert our Provider config into a PydanticAI Model instance.

    Handles Azure Entra ID auth (no API key) and standard OpenAI-compatible providers.
    """
    return build_model_from_string(agent.provider.model)


def build_model_from_string(model_str: str) -> Any:
    """Convert a model string (e.g. "azure/gpt-5-mini") to a PydanticAI Model.

    Handles Azure Entra ID auth, Copilot SDK, and standard provider string conversion.
    """
    if model_str.startswith("azure/"):
        return _build_azure_model(model_str)

    if model_str.startswith("copilot/"):
        return _build_copilot_model(model_str)

    # For non-Azure models, use PydanticAI's string-based model resolution
    # Convert our format "provider/model" to pydantic-ai format "provider:model"
    if "/" in model_str:
        provider, model_name = model_str.split("/", 1)
        return f"{provider}:{model_name}"

    return model_str


@functools.lru_cache(maxsize=8)
def _build_azure_model(model_str: str) -> Any:
    """Build an Azure OpenAI model with Entra ID or API key auth.

    Cached to reuse the same AsyncAzureOpenAI client across calls.
    """
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    deployment = model_str.removeprefix("azure/")
    azure_endpoint = os.environ.get("AZURE_API_BASE") or os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not azure_endpoint:
        msg = (
            "AZURE_API_BASE or AZURE_OPENAI_ENDPOINT environment variable is required "
            "for Azure OpenAI models"
        )
        raise ValueError(msg)

    # Check if API key is available
    api_key = os.environ.get("AZURE_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")

    if api_key:
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version="2024-07-01-preview",
        )
    else:
        # Use Entra ID (DefaultAzureCredential)
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AsyncAzureOpenAI

        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        client = AsyncAzureOpenAI(
            azure_endpoint=azure_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-07-01-preview",
        )

    return OpenAIChatModel(deployment, provider=OpenAIProvider(openai_client=client))


def _build_copilot_model(model_str: str) -> Any:
    """Build a CopilotModel backed by the GitHub Copilot SDK.

    Requires ``pytest-skill-engineering[copilot]`` to be installed.
    Auth is implicit via GITHUB_TOKEN or ``gh`` CLI login.
    """
    from pytest_skill_engineering.copilot.model import CopilotModel

    model_name = model_str.removeprefix("copilot/")
    return CopilotModel(model_name)


def build_mcp_toolsets(
    mcp_servers: list[MCPServer], *, max_retries: int = 1
) -> list[PydanticMCPServer]:
    """Convert our MCPServer configs into PydanticAI MCP toolsets."""
    toolsets: list[PydanticMCPServer] = []

    for cfg in mcp_servers:
        match cfg.transport:
            case "stdio":
                env = {**os.environ, **cfg.env} if cfg.env else None
                toolsets.append(
                    MCPServerStdio(
                        cfg.command[0],
                        args=[*cfg.command[1:], *cfg.args],
                        env=env,
                        cwd=cfg.cwd,
                        timeout=cfg.wait.timeout_ms / 1000,
                        max_retries=max_retries,
                    )
                )
            case "sse":
                assert cfg.url is not None
                toolsets.append(
                    MCPServerSSE(
                        cfg.url,
                        headers=cfg.headers or None,
                        timeout=cfg.wait.timeout_ms / 1000,
                        max_retries=max_retries,
                    )
                )
            case "streamable-http":
                assert cfg.url is not None
                toolsets.append(
                    MCPServerStreamableHTTP(
                        cfg.url,
                        headers=cfg.headers or None,
                        timeout=cfg.wait.timeout_ms / 1000,
                        max_retries=max_retries,
                    )
                )

    return toolsets


def build_system_prompt(agent: Agent) -> str | None:
    """Build the complete system prompt with skill content prepended."""
    parts: list[str] = []

    if agent.skill:
        parts.append(agent.skill.content)

    if agent.system_prompt:
        parts.append(agent.system_prompt)

    return "\n\n".join(parts) if parts else None


def _apply_tool_filter(
    toolsets: list[AbstractToolset],
    allowed_tools: list[str],
) -> list[AbstractToolset]:
    """Wrap each toolset with FilteredToolset to restrict to allowed tools only."""
    from pydantic_ai.toolsets import FilteredToolset

    allowed = set(allowed_tools)
    return [
        FilteredToolset(ts, filter_func=lambda _ctx, tool_def: tool_def.name in allowed)
        for ts in toolsets
    ]


def build_pydantic_agent(
    agent: Agent,
    toolsets: list[AbstractToolset],
) -> PydanticAgent[None, str]:
    """Create a PydanticAI Agent from our Agent config."""
    model = build_pydantic_model(agent)
    instructions = build_system_prompt(agent)

    # Apply allowed_tools filter if specified
    if agent.allowed_tools is not None:
        toolsets = _apply_tool_filter(toolsets, agent.allowed_tools)

    # Build model settings
    from pydantic_ai.settings import ModelSettings

    model_settings_kwargs: dict[str, Any] = {}
    if agent.provider.temperature is not None:
        model_settings_kwargs["temperature"] = agent.provider.temperature
    if agent.provider.max_tokens is not None:
        model_settings_kwargs["max_tokens"] = agent.provider.max_tokens

    settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None

    return PydanticAgent(
        model,
        instructions=instructions,
        toolsets=toolsets,
        model_settings=settings,
        retries=agent.retries,
    )


def build_usage_limits(agent: Agent) -> UsageLimits:
    """Build PydanticAI UsageLimits from our Agent config."""
    return UsageLimits(request_limit=agent.max_turns)


def adapt_result(
    pydantic_result: AgentRunResult[str],
    *,
    start_time: float,
    model: str,
    available_tools: list[ToolInfo],
    skill_info: SkillInfo | None,
    effective_system_prompt: str,
    session_context_count: int = 0,
) -> AgentResult:
    """Convert PydanticAI AgentRunResult into our AgentResult for reporting."""
    from pytest_skill_engineering.execution.cost import estimate_cost

    duration_ms = (time.perf_counter() - start_time) * 1000

    # Extract usage
    usage = pydantic_result.usage()
    input_tokens = usage.input_tokens or 0
    output_tokens = usage.output_tokens or 0
    token_usage = {
        "prompt": input_tokens,
        "completion": output_tokens,
    }

    cost_usd = estimate_cost(model, input_tokens, output_tokens)

    # Convert messages to our Turn format
    turns = _extract_turns(pydantic_result.all_messages())

    # Store PydanticAI messages directly for session continuity
    raw_messages = pydantic_result.all_messages()

    return AgentResult(
        turns=turns,
        success=True,
        duration_ms=duration_ms,
        token_usage=token_usage,
        cost_usd=cost_usd,
        _messages=raw_messages,
        session_context_count=session_context_count,
        available_tools=available_tools,
        skill_info=skill_info,
        effective_system_prompt=effective_system_prompt,
    )


def _extract_turns(messages: list[ModelMessage]) -> list[Turn]:
    """Convert PydanticAI message history into our Turn list.

    Extracts user prompts, assistant text, and tool calls into our Turn format.
    System prompts and tool return parts are intentionally skipped (they're
    infrastructure, not user-visible conversation turns).
    """
    turns: list[Turn] = []

    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    content = part.content if isinstance(part.content, str) else str(part.content)
                    turns.append(Turn(role="user", content=content))
                # SystemPromptPart and ToolReturnPart are intentionally skipped
        elif isinstance(msg, ModelResponse):
            tool_calls: list[ToolCall] = []
            text_content = ""

            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    # Parse args — could be string or dict
                    if isinstance(part.args, str):
                        try:
                            arguments = json.loads(part.args)
                        except (json.JSONDecodeError, TypeError):
                            arguments = {"raw": part.args}
                    else:
                        arguments = part.args if isinstance(part.args, dict) else {}

                    # Find matching ToolReturnPart in subsequent messages
                    tool_result = _extract_tool_result(messages, part.tool_call_id)

                    tool_calls.append(
                        ToolCall(
                            name=part.tool_name,
                            arguments=arguments,
                            result=tool_result.text,
                            image_content=tool_result.image_content,
                            image_media_type=tool_result.image_media_type,
                        )
                    )
                elif isinstance(part, TextPart):
                    text_content += part.content
                else:
                    _logger.debug("Skipping unhandled response part type: %s", type(part).__name__)

            turns.append(Turn(role="assistant", content=text_content, tool_calls=tool_calls))

    return turns


@dataclass
class _ToolResult:
    """Extracted tool result with optional image content."""

    text: str | None = None
    image_content: bytes | None = None
    image_media_type: str | None = None


def _extract_tool_result(messages: list[ModelMessage], tool_call_id: str | None) -> _ToolResult:
    """Extract the result of a tool call by its ID, handling multimodal content.

    For text/JSON content, returns text as before.
    For BinaryContent (images), extracts bytes and media_type and sets a
    human-readable text summary like "[image/png, 12345 bytes]".
    For sequences with mixed content, extracts text and image parts separately.

    PydanticAI moves binary content from ToolReturnPart to a companion
    UserPromptPart in the same ModelRequest (with "See file <id>" placeholder
    in the ToolReturnPart). We check both locations.
    """
    if not tool_call_id:
        return _ToolResult()

    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart) and part.tool_call_id == tool_call_id:
                    result = _process_tool_content(part.content)
                    # If no image found in ToolReturnPart, check companion
                    # UserPromptPart in the same message (PydanticAI moves
                    # binary content there with "This is file <id>:" prefix)
                    if result.image_content is None:
                        image = _extract_companion_image(msg)
                        if image is not None:
                            result.image_content = image.image_content
                            result.image_media_type = image.image_media_type
                    return result
    return _ToolResult()


def _process_tool_content(content: Any) -> _ToolResult:
    """Process tool return content, extracting text and image data."""
    # Check for multimodal content types (BinaryContent, ImageUrl, etc.)
    if isinstance(content, MULTI_MODAL_CONTENT_TYPES):
        return _process_multimodal(content)

    # Sequences may contain mixed text + images
    if isinstance(content, (list, tuple)):
        return _process_sequence(content)

    # Default: stringify
    return _ToolResult(text=str(content))


def _extract_companion_image(msg: ModelRequest) -> _ToolResult | None:
    """Extract binary image from a companion UserPromptPart in the same message.

    PydanticAI moves binary content (BinaryImage) from tool returns into a
    UserPromptPart with content like ["This is file <id>:", BinaryImage(...)].
    This function scans the message for such parts.
    """
    for part in msg.parts:
        if isinstance(part, UserPromptPart):
            content = part.content
            if isinstance(content, (list, tuple)):
                for item in content:
                    if isinstance(item, MULTI_MODAL_CONTENT_TYPES):
                        result = _process_multimodal(item)
                        if result.image_content is not None:
                            return result
            elif isinstance(content, MULTI_MODAL_CONTENT_TYPES):
                result = _process_multimodal(content)
                if result.image_content is not None:
                    return result
    return None


def _process_multimodal(content: Any) -> _ToolResult:
    """Process a single multimodal content item."""
    from pydantic_ai.messages import BinaryContent

    if isinstance(content, BinaryContent):
        size = len(content.data)
        media = str(content.media_type)
        return _ToolResult(
            text=f"[{media}, {size} bytes]",
            image_content=content.data,
            image_media_type=media,
        )

    # Other multimodal types (ImageUrl, AudioUrl, etc.)
    return _ToolResult(text=str(content))


def _process_sequence(content: list[Any] | tuple[Any, ...]) -> _ToolResult:
    """Process a sequence of content items, extracting text and first image."""
    text_parts: list[str] = []
    image_content: bytes | None = None
    image_media_type: str | None = None

    for item in content:
        if isinstance(item, MULTI_MODAL_CONTENT_TYPES):
            result = _process_multimodal(item)
            if result.image_content and image_content is None:
                image_content = result.image_content
                image_media_type = result.image_media_type
            if result.text:
                text_parts.append(result.text)
        elif isinstance(item, str):
            text_parts.append(item)
        else:
            text_parts.append(str(item))

    return _ToolResult(
        text="\n".join(text_parts) if text_parts else None,
        image_content=image_content,
        image_media_type=image_media_type,
    )


def extract_tool_info_from_messages(messages: list[ModelMessage]) -> list[str]:
    """Extract tool names that were called from message history."""
    tool_names: set[str] = set()
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    tool_names.add(part.tool_name)
    return list(tool_names)
