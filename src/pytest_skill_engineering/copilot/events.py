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
        session.shutdown         → Session terminated
        session.info             → Informational message
        session.model_change     → Model changed mid-session
        session.usage_info       → Session-level usage
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
from typing import TYPE_CHECKING, Any

from pytest_skill_engineering.copilot.result import (
    CopilotResult,
    ToolCall,
    Turn,
    UsageInfo,
)
from pytest_skill_engineering.core.result import SubagentInvocation

if TYPE_CHECKING:
    from copilot import SessionEvent

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
        self._subagent_start_times: dict[str, float] = {}
        self._permissions: list[dict[str, Any]] = []
        self._permission_requested: bool = False
        self._model_used: str | None = None
        self._error: str | None = None
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

        duration_ms = (time.monotonic() - self._start_time) * 1000
        has_error = self._error is not None

        return CopilotResult(
            turns=self._turns,
            success=not has_error,
            error=self._error,
            duration_ms=duration_ms,
            usage=self._usage,
            reasoning_traces=self._reasoning_traces,
            subagent_invocations=self._subagents,
            permission_requested=self._permission_requested,
            permissions=self._permissions,
            model_used=self._model_used,
            raw_events=self._raw_events,
            total_premium_requests=self._total_premium_requests,
        )

    # ── Assistant events ──

    def _handle_assistant_message(self, event: SessionEvent) -> None:
        """Handle complete assistant message.

        Each assistant.message is a complete message — flush any pending
        content and start a new turn.
        """
        # Flush any pending partial content first
        self._flush_assistant_turn()

        content = _get_data_field(event, "content", "")
        if content:
            self._current_assistant_content.append(content)

        # Check for tool_requests in the message
        # SDK returns ToolRequest dataclass objects, not dicts
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
                tc = ToolCall(name=name, arguments=arguments or {})
                self._pending_tool_calls[call_id] = tc
                self._current_tool_calls.append(tc)

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

        # Add a tool turn for reporting
        tool_name = _get_data_field(event, "tool_name", tc.name if tc else "unknown")
        result_text = tc.result if tc else str(result_data)
        self._turns.append(Turn(role="tool", content=f"[{tool_name}] {result_text or ''}"))

    # ── Subagent recording (used by runSubagent tool handler) ──

    def record_subagent_start(self, name: str) -> None:
        """Record a subagent invocation dispatched via the runSubagent tool."""
        self._subagent_start_times[name] = time.monotonic()
        self._subagents.append(SubagentInvocation(name=name, status="started"))

    def record_subagent_complete(self, name: str) -> None:
        """Mark a previously started subagent invocation as completed."""
        start = self._subagent_start_times.pop(name, None)
        duration = (time.monotonic() - start) * 1000 if start else None
        for sa in self._subagents:
            if sa.name == name and sa.status == "started":
                sa.status = "completed"
                sa.duration_ms = duration
                return

    def record_subagent_failed(self, name: str) -> None:
        """Mark a previously started subagent invocation as failed."""
        self._subagent_start_times.pop(name, None)
        for sa in self._subagents:
            if sa.name == name and sa.status == "started":
                sa.status = "failed"
                return

    # ── Subagent events ──

    def _handle_subagent_selected(self, event: SessionEvent) -> None:
        """Handle subagent selection."""
        name = _get_data_field(event, "eval_name", "unknown")
        self._subagents.append(SubagentInvocation(name=name, status="selected"))

    def _handle_subagent_started(self, event: SessionEvent) -> None:
        """Handle subagent execution start."""
        name = _get_data_field(event, "eval_name", "unknown")
        self._subagent_start_times[name] = time.monotonic()
        # Update existing or add new
        for sa in self._subagents:
            if sa.name == name and sa.status == "selected":
                sa.status = "started"
                return
        self._subagents.append(SubagentInvocation(name=name, status="started"))

    def _handle_subagent_completed(self, event: SessionEvent) -> None:
        """Handle subagent execution completion."""
        name = _get_data_field(event, "eval_name", "unknown")
        start = self._subagent_start_times.pop(name, None)
        duration = (time.monotonic() - start) * 1000 if start else None
        for sa in self._subagents:
            if sa.name == name and sa.status in ("selected", "started"):
                sa.status = "completed"
                sa.duration_ms = duration
                return
        self._subagents.append(
            SubagentInvocation(name=name, status="completed", duration_ms=duration)
        )

    def _handle_subagent_failed(self, event: SessionEvent) -> None:
        """Handle subagent execution failure."""
        name = _get_data_field(event, "eval_name", "unknown")
        for sa in self._subagents:
            if sa.name == name and sa.status in ("selected", "started"):
                sa.status = "failed"
                return
        self._subagents.append(SubagentInvocation(name=name, status="failed"))

    # ── Session events ──

    def _handle_session_start(self, event: SessionEvent) -> None:
        """Handle session start — capture model selection."""
        model = _get_data_field(event, "selected_model", None)
        if model:
            self._model_used = model

    def _handle_session_usage_info(self, event: SessionEvent) -> None:
        """Handle session-level usage summary including premium request count."""
        self._total_premium_requests = float(
            _get_data_field(event, "total_premium_requests", 0) or 0
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


def _get_data_field(event: SessionEvent, field: str, default: Any = None) -> Any:
    """Safely get a field from event.data (which has ~90 optional fields)."""
    return getattr(event.data, field, default)


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
    # User
    "user.message": EventMapper._handle_user_message,
    # Permissions
    "tool.user_requested": EventMapper._handle_permission,
}
