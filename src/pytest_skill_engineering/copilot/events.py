"""Map Copilot SDK SessionEvents to CopilotResult.

Converts the raw event stream from the Copilot SDK into structured
Turn/ToolCall objects for assertion and reporting.

SDK Event Types (38 values) grouped by what they map to:

    Tool lifecycle:
        tool.execution_start     → Start tracking a ToolCall
        tool.execution_complete  → Complete the ToolCall with result
        tool.execution_progress  → Progress update (logged)
        tool.user_requested      → User-initiated tool call

    Assistant output:
        assistant.message        → Assistant Turn with content
        assistant.message_delta  → Streaming delta (accumulated)
        assistant.reasoning      → Reasoning trace
        assistant.reasoning_delta → Streaming reasoning delta
        assistant.intent         → Intent declaration
        assistant.turn_start     → Turn boundary marker
        assistant.turn_end       → Turn boundary marker
        assistant.usage          → Token usage / cost

    Subagent routing:
        subagent.selected        → Subagent chosen
        subagent.started         → Subagent execution begins
        subagent.completed       → Subagent execution ends
        subagent.failed          → Subagent execution failed

    Session lifecycle:
        session.start            → Session metadata (model, etc.)
        session.resume           → Session resumed
        session.idle             → Eval finished processing
        session.error            → Error occurred
        session.shutdown         → Session terminated; carries premium request count
        session.info             → Informational message
        session.model_change     → Model changed mid-session
        session.usage_info       → Context-window usage (tokens/limit; no premium requests)
        session.handoff          → Session handoff
        session.truncation       → Context truncation
        session.compaction_start → Compaction started
        session.compaction_complete → Compaction completed
        session.snapshot_rewind  → Snapshot rewind

    User:
        user.message             → User Turn

    Other:
        skill.invoked            → Skill activation
        hook.start / hook.end    → Hook lifecycle
        system.message           → System message
        abort                    → Abort signal
        pending_messages.modified → Queue change
        unknown                  → Forward-compat catch-all
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_skill_engineering.copilot.contracts import SubagentStatus
from pytest_skill_engineering.copilot.result import (
    CopilotResult,
    SubagentInvocation,
    ToolCall,
    Turn,
    UsageInfo,
)

if TYPE_CHECKING:
    from copilot.generated.session_events import SessionEvent

logger = logging.getLogger(__name__)


class EventMapper:
    """Accumulates SDK events and builds a CopilotResult.

    Usage:
        mapper = EventMapper()
        for event in events:
            mapper.handle(event)
        result = mapper.build()
    """

    def __init__(self) -> None:
        self._turns: list[Turn] = []
        self._pending_tool_calls: dict[str, ToolCall] = {}  # tool_call_id → ToolCall
        self._pending_tool_start_times: dict[str, float] = {}
        self._current_assistant_content: list[str] = []
        self._current_tool_calls: list[ToolCall] = []
        self._current_tool_call_ids: set[str] = set()  # track call_ids in current turn
        self._usage: list[UsageInfo] = []
        self._reasoning_traces: list[str] = []
        self._reasoning_buffer: list[str] = []
        self._subagents: list[SubagentInvocation] = []
        self._subagents_by_invocation_id: dict[str, SubagentInvocation] = {}
        self._pending_selected_subagents: dict[str, deque[SubagentInvocation]] = {}
        self._open_subagent_invocations: dict[str, deque[str]] = {}
        self._subagent_start_times: dict[str, float] = {}
        self._tool_subagent_call_ids: dict[str, str] = {}  # call_id → agent_name
        self._permissions: list[dict[str, Any]] = []
        self._permission_requested: bool = False
        self._model_used: str | None = None
        self._error: str | None = None
        self._contract_errors: list[str] = []
        self._raw_events: list[Any] = []
        self._start_time: float = time.monotonic()
        self._total_premium_requests: float = 0.0

    def handle(self, event: SessionEvent) -> None:
        """Process a single SDK event."""
        self._raw_events.append(event)
        event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

        handler = _EVENT_HANDLERS.get(event_type)
        if handler:
            handler(self, event)
        else:
            logger.debug("Unhandled event type: %s", event_type)

    def build(self) -> CopilotResult:
        """Build the final CopilotResult from accumulated events."""
        # Flush any pending assistant content
        self._flush_assistant_turn()

        resolved_subagents = [subagent for subagent in self._subagents if subagent.invocation_id]
        unresolved_subagents = [
            subagent.name for subagent in self._subagents if not subagent.invocation_id
        ]
        if unresolved_subagents:
            self._record_contract_error(
                "Subagent selected event was not correlated to a tool_call_id: "
                + ", ".join(unresolved_subagents)
            )

        if self._contract_errors and self._error is None:
            self._error = "; ".join(self._contract_errors)

        duration_ms = (time.monotonic() - self._start_time) * 1000
        has_error = self._error is not None

        return CopilotResult(
            turns=self._turns,
            success=not has_error,
            error=self._error,
            duration_ms=duration_ms,
            usage=self._usage,
            reasoning_traces=self._reasoning_traces,
            subagent_invocations=resolved_subagents,
            permission_requested=self._permission_requested,
            permissions=self._permissions,
            model_used=self._model_used,
            raw_events=self._raw_events,
            total_premium_requests=self._total_premium_requests,
        )

    # ── Assistant events ──

    def _handle_assistant_message(self, event: SessionEvent) -> None:
        """Handle complete assistant message.

        The SDK fires both streaming deltas (accumulated via turn_end)
        AND a complete assistant.message with the same content. We must
        avoid creating duplicate turns.
        """
        content = _get_data_field(event, "content", "")

        # If we have accumulated delta content that hasn't been flushed
        # yet, the complete message supersedes it — clear and replace.
        if self._current_assistant_content:
            self._current_assistant_content.clear()
            if content:
                self._current_assistant_content.append(content)
        elif content:
            # Deltas were already flushed by turn_end — check if the
            # last turn already has this exact content to avoid duplication.
            if (
                self._turns
                and self._turns[-1].role == "assistant"
                and self._turns[-1].content == content
            ):
                # Already flushed by turn_end — skip
                pass
            else:
                self._current_assistant_content.append(content)

        # Check for tool_requests in the message
        # SDK returns ToolRequest dataclass objects, not dicts
        # NOTE: tool.execution_start events also create ToolCalls, so
        # we use _current_tool_call_ids to deduplicate.
        tool_requests = _get_data_field(event, "tool_requests", None)
        if tool_requests:
            for req in tool_requests:
                call_id = getattr(req, "tool_call_id", "") or ""
                name = getattr(req, "name", "unknown")
                arguments = getattr(req, "arguments", {})
                if isinstance(arguments, str):
                    import json

                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}
                if call_id and call_id not in self._current_tool_call_ids:
                    tc = ToolCall(name=name, arguments=arguments or {})
                    self._pending_tool_calls[call_id] = tc
                    self._current_tool_calls.append(tc)
                    self._current_tool_call_ids.add(call_id)

    def _handle_assistant_message_delta(self, event: SessionEvent) -> None:
        """Handle streaming delta — accumulate content."""
        delta = _get_data_field(event, "delta_content", "")
        if delta:
            self._current_assistant_content.append(delta)

    def _handle_assistant_reasoning(self, event: SessionEvent) -> None:
        """Handle complete reasoning trace."""
        text = _get_data_field(event, "reasoning_text", "")
        if text:
            # Flush any buffered deltas first
            if self._reasoning_buffer:
                self._reasoning_traces.append("".join(self._reasoning_buffer))
                self._reasoning_buffer.clear()
            self._reasoning_traces.append(text)

    def _handle_assistant_reasoning_delta(self, event: SessionEvent) -> None:
        """Handle streaming reasoning delta."""
        delta = _get_data_field(event, "delta_content", "")
        if delta:
            self._reasoning_buffer.append(delta)

    def _handle_assistant_turn_start(self, event: SessionEvent) -> None:
        """Mark the start of a new assistant turn."""
        # Flush previous turn if any
        self._flush_assistant_turn()

    def _handle_assistant_turn_end(self, event: SessionEvent) -> None:
        """Mark the end of an assistant turn."""
        # Flush reasoning buffer
        if self._reasoning_buffer:
            self._reasoning_traces.append("".join(self._reasoning_buffer))
            self._reasoning_buffer.clear()
        self._flush_assistant_turn()

    def _handle_assistant_usage(self, event: SessionEvent) -> None:
        """Handle token usage report."""
        model = _get_data_field(event, "model", "unknown")
        self._model_used = model
        input_tokens = int(_get_data_field(event, "input_tokens", 0) or 0)
        output_tokens = int(_get_data_field(event, "output_tokens", 0) or 0)
        self._usage.append(
            UsageInfo(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=int(_get_data_field(event, "cache_read_tokens", 0) or 0),
                duration_ms=_get_data_field(event, "duration", 0.0) or 0.0,
            )
        )

    # ── Tool events ──

    # Tool names that represent subagent dispatch (native SDK tools).
    _SUBAGENT_TOOL_NAMES = frozenset({"runSubagent", "task"})

    def _handle_tool_execution_start(self, event: SessionEvent) -> None:
        """Handle tool execution starting."""
        call_id = _get_data_field(event, "tool_call_id", "")
        name = _get_data_field(event, "tool_name", "unknown")
        arguments = _get_data_field(event, "arguments", {})

        if isinstance(arguments, str):
            import json

            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"raw": arguments}

        tc = ToolCall(name=name, arguments=arguments)
        self._pending_tool_calls[call_id] = tc
        self._pending_tool_start_times[call_id] = time.monotonic()

        # Associate with current assistant turn
        if call_id not in self._current_tool_call_ids:
            self._current_tool_call_ids.add(call_id)
            self._current_tool_calls.append(tc)

        # Detect subagent dispatch via native tool calls (runSubagent/task).
        # The SDK may or may not emit separate subagent.* events, so we
        # also track invocations here as a fallback.
        if name in self._SUBAGENT_TOOL_NAMES:
            agent_name = _resolve_tool_subagent_name(arguments)
            if not call_id:
                self._record_contract_error(f"{name} dispatch is missing tool_call_id")
            elif agent_name is None:
                self._record_contract_error(
                    f"{name} dispatch {call_id} is missing required agentSlug"
                )
            else:
                self._tool_subagent_call_ids[call_id] = agent_name
                self.record_subagent_start(invocation_id=call_id, name=agent_name)

    def _handle_tool_execution_complete(self, event: SessionEvent) -> None:
        """Handle tool execution completed."""
        call_id = _get_data_field(event, "tool_call_id", "")
        result_data = _get_data_field(event, "result", None)

        tc = self._pending_tool_calls.get(call_id)
        if tc:
            # Extract result text
            if result_data and hasattr(result_data, "content"):
                tc.result = str(result_data.content)
            elif isinstance(result_data, str):
                tc.result = result_data
            elif result_data is not None:
                tc.result = str(result_data)

            # Calculate duration
            start = self._pending_tool_start_times.pop(call_id, None)
            if start is not None:
                tc.duration_ms = (time.monotonic() - start) * 1000

            if not _get_data_field(event, "success", True):
                tc.error = _stringify_tool_error(_get_data_field(event, "error", None))

        # Complete subagent tracking from tool call
        agent_name = self._tool_subagent_call_ids.pop(call_id, None)
        if agent_name:
            if _get_data_field(event, "success", True):
                self.record_subagent_complete(invocation_id=call_id, name=agent_name)
            else:
                self.record_subagent_failed(invocation_id=call_id, name=agent_name)

        # Add a tool turn for reporting
        tool_name = _get_data_field(event, "tool_name", tc.name if tc else "unknown")
        result_text = tc.result if tc else str(result_data)
        self._turns.append(Turn(role="tool", content=f"[{tool_name}] {result_text or ''}"))

    # ── Subagent recording (used by runSubagent tool handler) ──

    def record_subagent_start(self, *, invocation_id: str, name: str) -> None:
        """Record a subagent invocation dispatched via a tool call."""
        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        self._enqueue_open_subagent(name=name, invocation_id=invocation_id)
        self._subagent_start_times.setdefault(invocation_id, time.monotonic())
        self._advance_subagent_status(invocation, "started")

    def record_subagent_complete(self, *, invocation_id: str, name: str) -> None:
        """Mark a previously started subagent invocation as completed."""
        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        duration = self._resolve_subagent_duration_ms(invocation_id=invocation_id)
        self._dequeue_open_subagent(name=name, invocation_id=invocation_id)
        self._advance_subagent_status(invocation, "completed", duration_ms=duration)

    def record_subagent_failed(self, *, invocation_id: str, name: str) -> None:
        """Mark a previously started subagent invocation as failed."""
        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        duration = self._resolve_subagent_duration_ms(invocation_id=invocation_id)
        self._dequeue_open_subagent(name=name, invocation_id=invocation_id)
        self._advance_subagent_status(invocation, "failed", duration_ms=duration)

    # ── Subagent events ──

    def _handle_subagent_selected(self, event: SessionEvent) -> None:
        """Handle subagent selection."""
        name = _require_subagent_name(event)
        if name is None:
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            self._record_contract_error(f"{event_type} is missing required agent_name")
            return

        invocation_id = self._peek_open_subagent(name)
        if invocation_id is None:
            pending = SubagentInvocation(invocation_id="", name=name, status="selected")
            self._subagents.append(pending)
            self._pending_selected_subagents.setdefault(name, deque()).append(pending)
            return

        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        self._advance_subagent_status(invocation, "selected")

    def _handle_subagent_started(self, event: SessionEvent) -> None:
        """Handle subagent execution start."""
        name = _require_subagent_name(event)
        invocation_id = _require_invocation_id(event)
        if name is None or invocation_id is None:
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            self._record_contract_error(
                f"{event_type} is missing required subagent correlation fields"
            )
            return

        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        self._enqueue_open_subagent(name=name, invocation_id=invocation_id)
        self._subagent_start_times.setdefault(invocation_id, time.monotonic())
        self._advance_subagent_status(invocation, "started")

    def _handle_subagent_completed(self, event: SessionEvent) -> None:
        """Handle subagent execution completion."""
        name = _require_subagent_name(event)
        invocation_id = _require_invocation_id(event)
        if name is None or invocation_id is None:
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            self._record_contract_error(
                f"{event_type} is missing required subagent correlation fields"
            )
            return

        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        self._dequeue_open_subagent(name=name, invocation_id=invocation_id)
        duration = _duration_to_ms(_get_data_field(event, "duration", None))
        if duration is None:
            duration = self._resolve_subagent_duration_ms(invocation_id=invocation_id)
        self._advance_subagent_status(invocation, "completed", duration_ms=duration)

    def _handle_subagent_failed(self, event: SessionEvent) -> None:
        """Handle subagent execution failure."""
        name = _require_subagent_name(event)
        invocation_id = _require_invocation_id(event)
        if name is None or invocation_id is None:
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            self._record_contract_error(
                f"{event_type} is missing required subagent correlation fields"
            )
            return

        invocation = self._ensure_subagent_invocation(invocation_id=invocation_id, name=name)
        self._dequeue_open_subagent(name=name, invocation_id=invocation_id)
        duration = _duration_to_ms(_get_data_field(event, "duration", None))
        if duration is None:
            duration = self._resolve_subagent_duration_ms(invocation_id=invocation_id)
        self._advance_subagent_status(invocation, "failed", duration_ms=duration)

    # ── Session events ──

    def _handle_session_start(self, event: SessionEvent) -> None:
        """Handle session start — capture model selection."""
        model = _get_data_field(event, "selected_model", None)
        if model:
            self._model_used = model

    def _handle_session_usage_info(self, event: SessionEvent) -> None:
        """Handle session-level context-window usage (tokens/limit).

        SDK 1.x's ``session.usage_info`` no longer carries a premium-request
        count (it's context-window stats only). Retained as a documented
        no-op handler so the event isn't logged as unhandled; see
        ``_handle_session_shutdown`` for premium requests.
        """

    def _handle_session_shutdown(self, event: SessionEvent) -> None:
        """Handle session shutdown — capture the total premium request count.

        KNOWN GAP (SDK 1.0.9): ``_total_premium_requests`` exists on
        ``SessionShutdownData`` per the generated schema, but empirically
        ``session.shutdown`` is never delivered to ``session.on()`` listeners
        via the ``client.stop()`` teardown path this runner uses — verified
        by capturing every event in a live session and finding no field
        containing "premium" anywhere in the stream. So ``premium_requests``
        stays 0.0 in practice today. This handler is kept because it's
        schema-correct and harmless, in case a future SDK version emits the
        event (or an alternate teardown path does). If this still reads 0.0
        after upgrading github-copilot-sdk, check whether the SDK now
        exposes a public usage/metrics RPC instead of relying on this event.
        """
        self._total_premium_requests = float(
            _get_data_field(event, "_total_premium_requests", 0) or 0
        )

    def _handle_session_error(self, event: SessionEvent) -> None:
        """Handle session error."""
        msg = _get_data_field(event, "message", "Unknown error")
        error_type = _get_data_field(event, "error_type", "")
        self._error = f"{error_type}: {msg}" if error_type else msg

    # ── User events ──

    def _handle_user_message(self, event: SessionEvent) -> None:
        """Handle user message — create a user turn."""
        content = _get_data_field(event, "content", "")
        if content:
            self._turns.append(Turn(role="user", content=content))

    # ── Permission events ──

    def _handle_permission(self, event: SessionEvent) -> None:
        """Handle permission request."""
        self._permission_requested = True
        self._permissions.append(
            {
                "type": _get_data_field(event, "permission_type", "unknown"),
                "tool": _get_data_field(event, "tool_name", None),
                "message": _get_data_field(event, "message", ""),
            }
        )

    # ── Internal helpers ──

    def _flush_assistant_turn(self) -> None:
        """Flush accumulated assistant content into a Turn."""
        if self._current_assistant_content or self._current_tool_calls:
            content = "".join(self._current_assistant_content)
            self._turns.append(
                Turn(
                    role="assistant",
                    content=content,
                    tool_calls=list(self._current_tool_calls),
                )
            )
            self._current_assistant_content.clear()
            self._current_tool_calls.clear()
            self._current_tool_call_ids.clear()

    def _ensure_subagent_invocation(
        self,
        *,
        invocation_id: str,
        name: str,
    ) -> SubagentInvocation:
        """Get or create a subagent invocation keyed by invocation ID."""
        existing = self._subagents_by_invocation_id.get(invocation_id)
        if existing is not None:
            if existing.name != name:
                self._record_contract_error(
                    "Subagent invocation "
                    f"{invocation_id} changed name from {existing.name} to {name}"
                )
            return existing

        pending = self._consume_pending_selected(name=name)
        if pending is not None:
            pending.invocation_id = invocation_id
            self._subagents_by_invocation_id[invocation_id] = pending
            return pending

        invocation = SubagentInvocation(invocation_id=invocation_id, name=name, status="started")
        self._subagents.append(invocation)
        self._subagents_by_invocation_id[invocation_id] = invocation
        return invocation

    def _consume_pending_selected(self, *, name: str) -> SubagentInvocation | None:
        pending = self._pending_selected_subagents.get(name)
        if not pending:
            return None
        invocation = pending.popleft()
        if not pending:
            self._pending_selected_subagents.pop(name, None)
        return invocation

    def _enqueue_open_subagent(self, *, name: str, invocation_id: str) -> None:
        queue = self._open_subagent_invocations.setdefault(name, deque())
        if invocation_id not in queue:
            queue.append(invocation_id)

    def _peek_open_subagent(self, name: str) -> str | None:
        queue = self._open_subagent_invocations.get(name)
        if not queue:
            return None
        return queue[0]

    def _dequeue_open_subagent(self, *, name: str, invocation_id: str) -> None:
        queue = self._open_subagent_invocations.get(name)
        if not queue:
            return
        try:
            queue.remove(invocation_id)
        except ValueError:
            return
        if not queue:
            self._open_subagent_invocations.pop(name, None)

    def _advance_subagent_status(
        self,
        invocation: SubagentInvocation,
        status: SubagentStatus,
        *,
        duration_ms: float | None = None,
    ) -> None:
        status_order = {"selected": 0, "started": 1, "completed": 2, "failed": 2}
        if status_order[status] < status_order[invocation.status]:
            return
        if invocation.status in {"completed", "failed"} and invocation.status != status:
            self._record_contract_error(
                "Subagent invocation "
                f"{invocation.invocation_id} ended twice with conflicting states"
            )
            return
        invocation.status = status
        if duration_ms is not None:
            invocation.duration_ms = duration_ms

    def _resolve_subagent_duration_ms(self, *, invocation_id: str) -> float | None:
        start = self._subagent_start_times.pop(invocation_id, None)
        if start is None:
            return None
        return (time.monotonic() - start) * 1000

    def _record_contract_error(self, message: str) -> None:
        if message not in self._contract_errors:
            self._contract_errors.append(message)


def _get_data_field(event: SessionEvent, field: str, default: Any = None) -> Any:
    """Safely get a field from event.data (which has ~90 optional fields)."""
    return getattr(event.data, field, default)


def _require_subagent_name(event: SessionEvent) -> str | None:
    """Extract the current SDK subagent name field."""
    name = _get_data_field(event, "agent_name", None)
    if isinstance(name, str) and name:
        return name
    return None


def _require_invocation_id(event: SessionEvent) -> str | None:
    """Extract the current SDK subagent invocation correlation field."""
    invocation_id = _get_data_field(event, "tool_call_id", None)
    if isinstance(invocation_id, str) and invocation_id:
        return invocation_id
    return None


def _resolve_tool_subagent_name(arguments: Any) -> str | None:
    """Extract the current dispatch tool key for the target custom agent."""
    if not isinstance(arguments, dict):
        return None
    for key in ("agentSlug", "agent_type", "name"):
        agent_slug = arguments.get(key)
        if isinstance(agent_slug, str) and agent_slug:
            return agent_slug
    return None


def _duration_to_ms(value: Any) -> float | None:
    """Convert current SDK duration values to milliseconds."""
    if isinstance(value, timedelta):
        return value.total_seconds() * 1000
    if isinstance(value, (float, int)):
        return float(value)
    return None


def _stringify_tool_error(error: Any) -> str | None:
    """Extract a readable tool error message."""
    if error is None:
        return None
    message = getattr(error, "message", None)
    if isinstance(message, str) and message:
        return message
    return str(error)


# ── Event type → handler dispatch table ──

_EVENT_HANDLERS: dict[str, Any] = {
    # Assistant
    "assistant.message": EventMapper._handle_assistant_message,
    "assistant.message_delta": EventMapper._handle_assistant_message_delta,
    "assistant.reasoning": EventMapper._handle_assistant_reasoning,
    "assistant.reasoning_delta": EventMapper._handle_assistant_reasoning_delta,
    "assistant.turn_start": EventMapper._handle_assistant_turn_start,
    "assistant.turn_end": EventMapper._handle_assistant_turn_end,
    "assistant.usage": EventMapper._handle_assistant_usage,
    # Tools
    "tool.execution_start": EventMapper._handle_tool_execution_start,
    "tool.execution_complete": EventMapper._handle_tool_execution_complete,
    # Subagents
    "subagent.selected": EventMapper._handle_subagent_selected,
    "subagent.started": EventMapper._handle_subagent_started,
    "subagent.completed": EventMapper._handle_subagent_completed,
    "subagent.failed": EventMapper._handle_subagent_failed,
    # Session
    "session.start": EventMapper._handle_session_start,
    "session.error": EventMapper._handle_session_error,
    "session.usage_info": EventMapper._handle_session_usage_info,
    "session.shutdown": EventMapper._handle_session_shutdown,
    # User
    "user.message": EventMapper._handle_user_message,
    # Permissions
    "tool.user_requested": EventMapper._handle_permission,
}
