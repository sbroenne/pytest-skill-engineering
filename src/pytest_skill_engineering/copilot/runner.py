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
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from pytest_skill_engineering.copilot.client import (
    approve_all_permissions,
    create_client,
    stop_client,
)
from pytest_skill_engineering.copilot.contracts import CopilotEvalConfig
from pytest_skill_engineering.copilot.controls import RunControls
from pytest_skill_engineering.copilot.events import EventMapper
from pytest_skill_engineering.copilot.requests import RequestAuditHandler
from pytest_skill_engineering.copilot.result import CopilotResult, StopReason
from pytest_skill_engineering.copilot.skills import discover_requested_skills, requested_skill_files
from pytest_skill_engineering.core.result import SkillDiscovery

if TYPE_CHECKING:
    from copilot.client import CopilotClient
    from copilot.generated.session_events import SessionEvent
    from copilot.session import CopilotSession

logger = logging.getLogger(__name__)


async def run_copilot(agent: CopilotEvalConfig, prompt: str) -> CopilotResult:
    """Execute a prompt against GitHub Copilot and return structured results.

    This is the primary entry point for test execution. It manages the full
    lifecycle: client start → session creation → prompt execution → event
    capture → client cleanup.

    Each call makes one execution attempt. Failures retain their captured
    evidence and are returned without starting a replacement session.

    Authentication is resolved in this order:
    1. ``GITHUB_TOKEN`` environment variable (ideal for CI)
    2. ``GH_TOKEN`` environment variable
    3. Logged-in user via ``gh`` CLI / OAuth (local development)

    Args:
        agent: CopilotEval configuration.
        prompt: The prompt to send to Copilot.

    Returns:
        CopilotResult with all captured events, tool calls, usage, etc.

    """
    mapper = EventMapper()
    controls = RunControls(agent.max_tool_calls)
    capture_requests = agent.audit_requests or agent.image_detail is not None
    audit = (
        RequestAuditHandler(
            image_detail=agent.image_detail,
            audit=agent.audit_requests,
            inspect_requests=capture_requests,
        )
        if capture_requests or agent.max_tool_calls is not None
        else None
    )
    storage: TemporaryDirectory[str] | None = None
    client: CopilotClient | None = None
    session: CopilotSession | None = None
    execution: asyncio.Task[None] | None = None
    budget_abort: asyncio.Task[None] | None = None
    watchers: list[asyncio.Task[bool]] = []
    reason: StopReason = "completed"
    error: str | None = None
    cleanup_errors: list[str] = []
    skill_discovery: SkillDiscovery | None = None
    send_started = False
    try:
        session_config = agent.build_session_config()
        skill_directories = session_config.get("skill_directories") or []
        requested_skills: dict[Path, str] = {}
        if skill_directories:
            skill_discovery = SkillDiscovery()
            if not isinstance(skill_directories, list):
                raise ValueError("skill_directories must be a list of directory paths")
            requested_skills = requested_skill_files(skill_directories)
            session_config["skill_directories"] = [
                str(Path(directory).resolve()) for directory in skill_directories
            ]
        caller_hooks = dict(session_config.get("hooks") or {})
        session_config["hooks"] = dict(caller_hooks)
        # Empty mode must not read persona instruction files or inject tools.
        if agent.client_mode != "empty":
            agent.persona.apply(agent, session_config, mapper, run_copilot)
        controls.install(session_config, caller_hooks)
        if agent.auto_confirm and "on_permission_request" not in session_config:
            session_config["on_permission_request"] = approve_all_permissions

        caller_event = session_config.get("on_event")

        def capture(event: SessionEvent) -> None:
            nonlocal budget_abort
            mapper.handle(event)
            if controls.observe(event) and session is not None:
                if audit is not None:
                    audit.stop_forwarding()
                logger.info(
                    "Aborting Copilot session: phase=tool_budget_exceeded admitted=%d "
                    "started=%d completed=%d handlers_started=%d handlers_finished=%d",
                    controls.admitted,
                    controls.started,
                    controls.completed,
                    controls.handlers_started,
                    controls.handlers_finished,
                )
                budget_abort = asyncio.create_task(session.abort())
            if caller_event is not None:
                caller_event(event)

        session_config["on_event"] = capture
        if agent.client_mode == "empty":
            storage = TemporaryDirectory(prefix="pytest-copilot-")
        client = create_client(
            agent.working_directory or ".",
            mode=agent.client_mode,
            base_directory=storage.name if storage else None,
            request_handler=audit,
        )

        async def execute() -> None:
            nonlocal session, send_started
            assert client is not None
            async with asyncio.timeout(min(60, agent.timeout_s)):
                await client.start()
            async with asyncio.timeout(min(30, agent.timeout_s)):
                session = await client.create_session(**session_config)
                if skill_discovery is not None:
                    await discover_requested_skills(
                        session,
                        requested_skills,
                        session_config.get("disabled_skills") or [],
                        skill_discovery,
                    )
            send_started = True
            await session.send_and_wait(prompt, timeout=agent.timeout_s)

        execution = asyncio.create_task(execute())
        watchers = [
            asyncio.create_task(controls.budget_exceeded.wait()),
            asyncio.create_task(controls.failed.wait()),
        ]
        if audit is not None:
            watchers.append(asyncio.create_task(audit.failed.wait()))
        done, _ = await asyncio.wait(
            [execution, *watchers], timeout=agent.timeout_s, return_when=asyncio.FIRST_COMPLETED
        )
        if audit is not None and audit.failed.is_set():
            reason, error = "request_audit_error", audit.error
        elif controls.failed.is_set():
            reason, error = "execution_error", controls.error
        elif controls.budget_exceeded.is_set():
            reason = "tool_budget_exceeded"
            error = f"Tool-call budget exhausted ({agent.max_tool_calls})"
        elif execution in done:
            await execution
        else:
            raise TimeoutError

    except TimeoutError:
        reason, error = "timeout", f"Timeout (eval limit {agent.timeout_s}s)"
    except Exception as exc:
        logger.error("Copilot execution failed: %s", exc)
        reason, error = "execution_error", str(exc)
        if skill_discovery is not None and not skill_discovery.complete:
            error = f"Skill setup failed before model execution: {exc}"
            skill_discovery.errors.append(error)
    finally:
        controls.closed = True
        for watcher in watchers:
            watcher.cancel()
        if watchers:
            await asyncio.gather(*watchers, return_exceptions=True)
        if budget_abort is not None:
            try:
                await asyncio.wait_for(budget_abort, timeout=30)
            except Exception as exc:
                logger.error("Failed to abort Copilot session at budget barrier", exc_info=True)
                cleanup_errors.append(f"Session abort failed: {type(exc).__name__}")
        elif session is not None and (
            error is not None or execution is None or not execution.done()
        ):
            logger.info(
                "Aborting Copilot session: phase=%s admitted=%d started=%d completed=%d "
                "handlers_started=%d handlers_finished=%d",
                reason,
                controls.admitted,
                controls.started,
                controls.completed,
                controls.handlers_started,
                controls.handlers_finished,
            )
            try:
                await asyncio.wait_for(session.abort(), timeout=30)
            except Exception as exc:
                logger.error("Failed to abort Copilot session", exc_info=True)
                cleanup_errors.append(f"Session abort failed: {type(exc).__name__}")
        if execution is not None:
            if not execution.done():
                execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
        cleanup_errors.extend(await controls.drain())
        if audit is not None:
            try:
                await audit.aclose()
            except Exception as exc:
                logger.error("Failed to close model request transport", exc_info=True)
                cleanup_errors.append(f"Request transport cleanup failed: {type(exc).__name__}")
        if client is not None:
            cleanup_errors.extend(await stop_client(client))
        if storage is not None:
            try:
                storage.cleanup()
            except OSError as exc:
                logger.error("Failed to remove isolated runtime storage", exc_info=True)
                cleanup_errors.append(f"Isolated storage cleanup failed: {type(exc).__name__}")

    result = mapper.build()
    result.agent = agent
    result.skill_discovery = skill_discovery
    result.tool_calls_admitted = controls.admitted
    if result.capture_errors:
        result.capture_errors.extend(controls.incomplete_diagnostics(abort_phase=reason))
    if audit is not None and capture_requests:
        result.request_audit = list(audit.records)
        if audit.error or (send_started and not audit.observed_requests):
            audit_error = audit.error or "No outbound model requests captured; audit unsupported"
            result.capture_errors.append(audit_error)
            if reason == "completed" or audit.error:
                reason, error = "request_audit_error", audit_error
    if cleanup_errors:
        result.capture_errors.extend(cleanup_errors)
        reason = "cleanup_error"
    errors = [message for message in [result.error, error, *cleanup_errors] if message]
    if result.capture_errors:
        errors.extend(message for message in result.capture_errors if message not in errors)
    result.error = "; ".join(errors) or None
    result.success = result.error is None
    result.stop_reason = (
        "execution_error" if reason == "completed" and not result.success else reason
    )
    return result
