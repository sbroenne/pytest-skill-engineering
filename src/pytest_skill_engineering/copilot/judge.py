"""Shared Copilot SDK judge utility for LLM-as-judge evaluations.

Provides a common interface for calling the Copilot SDK with judge prompts
and parsing responses. Used by llm_assert, llm_score, clarification detection,
and insights generation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import pattern — copilot SDK may not be installed
_CopilotClient: type[Any] | None = None


def _get_copilot_client() -> type[Any]:
    """Lazy-load CopilotClient to avoid import errors when SDK not installed."""
    global _CopilotClient  # noqa: PLW0603
    if _CopilotClient is None:
        try:
            from copilot import CopilotClient as _Client  # noqa: PLC0415

            _CopilotClient = _Client
        except ImportError as exc:
            msg = (
                "github-copilot-sdk is required for Copilot-based judge calls. "
                "Install with: uv add pytest-skill-engineering[copilot]"
            )
            raise ImportError(msg) from exc
    return _CopilotClient


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
        ImportError: If github-copilot-sdk is not installed.
        TimeoutError: If the session takes longer than timeout_seconds.
        RuntimeError: If the Copilot CLI fails to start or session errors.
    """
    from copilot import SubprocessConfig  # noqa: PLC0415

    CopilotClient = _get_copilot_client()

    subprocess_config = SubprocessConfig(
        cwd=".",
        log_level="warning",
    )

    client = CopilotClient(subprocess_config, auto_start=True)

    try:
        # Hard timeout on startup — CLI must start within 60s
        await asyncio.wait_for(client.start(), timeout=60)

        # Build session config
        session_config: dict[str, Any] = {}
        if model is not None:
            session_config["model"] = model

        # Create session
        session = await asyncio.wait_for(
            client.create_session(**session_config),
            timeout=30,
        )

        # Collect response chunks
        response_parts: list[str] = []

        def on_event(event: Any) -> None:
            """Collect assistant responses from events."""
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            if event_type == "assistant.response":
                data = event.data if hasattr(event, "data") else {}
                content = data.get("content", "")
                if content:
                    response_parts.append(content)

        session.on(on_event)

        # Send prompt and wait for completion
        await asyncio.wait_for(
            session.send_and_wait(prompt, timeout=timeout_seconds),
            timeout=timeout_seconds,
        )

        # Join all response parts
        return "".join(response_parts)

    except TimeoutError:
        logger.error("Copilot judge timed out after %ss", timeout_seconds)
        raise
    except Exception as exc:
        logger.error("Copilot judge failed: %s", exc)
        raise RuntimeError(f"Copilot judge execution failed: {exc}") from exc
    finally:
        try:
            await client.stop()
        except Exception:
            logger.warning("Failed to stop Copilot CLI cleanly, force stopping")
            await client.force_stop()
