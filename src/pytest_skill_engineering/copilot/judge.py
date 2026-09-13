"""Shared Copilot SDK judge utility for LLM-as-judge evaluations.

Provides a common interface for calling the Copilot SDK with judge prompts
and parsing responses. Used by llm_assert, llm_score, and insights generation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from copilot.generated.session_events import SessionEvent

from pytest_skill_engineering.copilot.client import (
    approve_all_permissions,
    create_client,
    stop_client,
)

logger = logging.getLogger(__name__)


def _get_data_field(event: Any, field: str, default: Any = None) -> Any:
    """Safely get a field from SDK event data objects."""
    return getattr(event.data, field, default)


async def copilot_judge(
    prompt: str,
    *,
    model: str | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    """Call Copilot SDK with a judge prompt and return the response text.

    Creates a minimal Copilot session, sends the prompt, and returns the
    assistant's final response. Designed for LLM-as-judge evaluations.

    Args:
        prompt: The evaluation prompt to send to the judge.
        model: Model to use (None = Copilot's default).
        timeout_seconds: Timeout for the session execution.

    Returns:
        The assistant's final response text.

    Raises:
        TimeoutError: If the session takes longer than timeout_seconds.
        RuntimeError: If the Copilot CLI fails to start or session errors.
    """
    client = create_client()

    try:
        # Hard timeout on startup — CLI must start within 60s
        await asyncio.wait_for(client.start(), timeout=60)

        # Build session config
        session_config: dict[str, Any] = {
            "on_permission_request": approve_all_permissions,
            "enable_config_discovery": False,
        }
        if model is not None:
            session_config["model"] = model

        response_parts: list[str] = []
        completed_response = ""

        def on_event(event: SessionEvent) -> None:
            """Collect assistant responses from events."""
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

            nonlocal completed_response

            if event_type == "assistant.message_delta":
                content = _get_data_field(event, "delta_content", "")
                if content:
                    response_parts.append(content)
                return

            if event_type == "assistant.message":
                content = _get_data_field(event, "content", "")
                if content:
                    completed_response = content
                return

            if event_type == "assistant.turn_end" and response_parts and not completed_response:
                completed_response = "".join(response_parts)

        session_config["on_event"] = on_event
        session = await asyncio.wait_for(
            client.create_session(**session_config),
            timeout=30,
        )

        # Send prompt and wait for completion
        await asyncio.wait_for(
            session.send_and_wait(prompt, timeout=timeout_seconds),
            timeout=timeout_seconds,
        )

        if completed_response:
            return completed_response

        return "".join(response_parts)

    except TimeoutError:
        logger.error("Copilot judge timed out after %ss", timeout_seconds)
        raise
    except Exception as exc:
        logger.error("Copilot judge failed: %s", exc)
        raise RuntimeError(f"Copilot judge execution failed: {exc}") from exc
    finally:
        await stop_client(client)
