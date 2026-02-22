"""CopilotRunner — Execute prompts against GitHub Copilot directly via SDK.

This is the core execution engine. It:
1. Creates a CopilotClient and starts the CLI server
2. Creates a session with the agent's config
3. Sends the prompt and captures ALL events
4. Maps events to a CopilotResult via EventMapper
5. Cleans up the client

No LiteLLM. No outer agent. One LLM. Direct SDK access.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, cast

from pytest_skill_engineering.copilot.events import EventMapper

CopilotClient: Any
try:
    from copilot import CopilotClient as _SdkCopilotClient
except ImportError as _exc:
    _import_error = _exc

    class _UnavailableCopilotClient:
        """Placeholder when github-copilot-sdk is not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            msg = (
                "github-copilot-sdk is required for Copilot agent testing. "
                "Install with: uv add pytest-skill-engineering[copilot]"
            )
            raise ImportError(msg) from _import_error

    CopilotClient = _UnavailableCopilotClient
else:
    CopilotClient = _SdkCopilotClient

if TYPE_CHECKING:
    from copilot import CopilotSession, SessionEvent
    from copilot.types import CopilotClientOptions

    from pytest_skill_engineering.copilot.eval import CopilotEval
    from pytest_skill_engineering.copilot.result import CopilotResult

logger = logging.getLogger(__name__)


async def run_copilot(agent: CopilotEval, prompt: str) -> CopilotResult:
    """Execute a prompt against GitHub Copilot and return structured results.

    This is the primary entry point for test execution. It manages the full
    lifecycle: client start → session creation → prompt execution → event
    capture → client cleanup.

    Retries on transient SDK errors (fetch failed, model list errors) up to
    ``agent.max_retries`` times with ``agent.retry_delay_s`` delay between
    attempts.

    Authentication is resolved in this order:
    1. ``GITHUB_TOKEN`` environment variable (ideal for CI)
    2. Logged-in user via ``gh`` CLI / OAuth (local development)

    Args:
        agent: CopilotEval configuration.
        prompt: The prompt to send to Copilot.

    Returns:
        CopilotResult with all captured events, tool calls, usage, etc.

    Raises:
        TimeoutError: If the prompt takes longer than agent.timeout_s.
        RuntimeError: If the Copilot CLI fails to start.
    """
    last_result: CopilotResult | None = None

    for attempt in range(1, agent.max_retries + 2):  # +2: 1 initial + max_retries
        result = await _run_copilot_once(agent, prompt)
        result.agent = agent  # Back-reference for automated report stashing

        if result.success or not _is_transient_error(result.error):
            return result

        last_result = result

        if attempt <= agent.max_retries:
            logger.warning(
                "Transient error on attempt %d/%d: %s — retrying in %ss",
                attempt,
                agent.max_retries + 1,
                result.error,
                agent.retry_delay_s,
            )
            await asyncio.sleep(agent.retry_delay_s)

    # All retries exhausted — return last result
    return cast("CopilotResult", last_result)


_TRANSIENT_PATTERNS = (
    "fetch failed",
    "Failed to list models",
    "ECONNREFUSED",
    "ECONNRESET",
    "ETIMEDOUT",
    "socket hang up",
    "SDK TimeoutError",
)


def _is_transient_error(error: str | None) -> bool:
    """Check if an error message matches a known transient SDK pattern."""
    if not error:
        return False
    return any(pattern in error for pattern in _TRANSIENT_PATTERNS)


async def _run_copilot_once(agent: "CopilotEval", prompt: str) -> "CopilotResult":
    """Execute a single attempt of a prompt against GitHub Copilot."""
    client_options: dict[str, Any] = {
        "cwd": agent.working_directory or ".",
        "auto_start": True,
        "log_level": "warning",
    }

    # Pass GITHUB_TOKEN from environment for CI authentication
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        client_options["github_token"] = github_token
        logger.info("Using GITHUB_TOKEN from environment for authentication")

    client = CopilotClient(options=cast("CopilotClientOptions", client_options))

    mapper = EventMapper()
    loop = asyncio.get_running_loop()
    _start = loop.time()

    try:
        # Hard timeout on startup — CLI must start within 60s.
        await asyncio.wait_for(client.start(), timeout=60)
        logger.info("Copilot CLI started")

        # Build session config from agent
        session_config = agent.build_session_config()

        # Apply the persona: injects polyfill tools and system-message
        # additions that match the target IDE environment.
        agent.persona.apply(agent, session_config, mapper)

        # Install permission handler if auto_confirm is enabled
        if agent.auto_confirm:
            session_config["on_permission_request"] = _auto_approve_handler

        # Hard timeout on session creation — 30s is generous.
        session: CopilotSession = await asyncio.wait_for(
            client.create_session(session_config),  # type: ignore[arg-type]
            timeout=30,
        )
        logger.info("Session created: %s", session.session_id)

        # Register event listener — captures ALL events
        session.on(mapper.handle)

        # Send prompt and wait for completion.
        # Pass timeout to both send_and_wait (SDK-internal idle wait)
        # and asyncio.wait_for (hard outer limit).
        result_event: SessionEvent | None = await asyncio.wait_for(
            session.send_and_wait({"prompt": prompt}, timeout=agent.timeout_s),
            timeout=agent.timeout_s,
        )

        # If send_and_wait returned a final event, process it too
        if result_event is not None:
            mapper.handle(result_event)

        logger.info("Prompt execution complete")

    except TimeoutError:
        elapsed = loop.time() - _start
        # Distinguish our asyncio.wait_for timeout from SDK-internal timeouts.
        # If elapsed is within 90% of timeout_s, it's likely our timeout.
        # Otherwise, the SDK raised TimeoutError internally.
        if elapsed >= agent.timeout_s * 0.9:
            msg = f"Timeout after {agent.timeout_s}s"
        else:
            msg = f"SDK TimeoutError after {elapsed:.0f}s (limit was {agent.timeout_s}s)"
        logger.error("Prompt execution timed out: %s", msg)
        result = mapper.build()
        result.success = False
        result.error = msg
        return result

    except Exception as exc:
        logger.error("Copilot execution failed: %s", exc)
        result = mapper.build()
        result.success = False
        result.error = str(exc)
        return result

    finally:
        try:
            await client.stop()
        except Exception:
            logger.warning("Failed to stop Copilot CLI cleanly, force stopping")
            await client.force_stop()

    return mapper.build()


def _auto_approve_handler(request: dict, context: dict[str, str]) -> dict:
    """Auto-approve all permission requests for deterministic testing.

    Args:
        request: PermissionRequest TypedDict with kind, toolCallId, etc.
        context: Additional context from the SDK.

    Returns:
        PermissionRequestResult with kind="approved".
    """
    return {"kind": "approved"}
