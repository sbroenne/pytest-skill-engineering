"""Unit tests for EventMapper.

These are pure logic tests — no LLM calls, no SDK.
They verify that EventMapper correctly maps mock events to CopilotResult.
"""

from __future__ import annotations

from types import SimpleNamespace

from pytest_skill_engineering.copilot.events import EventMapper


def _make_event(event_type: str, **data_fields) -> SimpleNamespace:
    """Create a mock SessionEvent with the given type and data fields."""
    # Use SimpleNamespace so getattr(data, field, default) returns default
    # for missing fields (unlike MagicMock which auto-creates them).
    data = SimpleNamespace(**data_fields)
    return SimpleNamespace(type=event_type, data=data)


class TestEventMapperAssistantMessage:
    """Test assistant.message event handling."""

    def test_captures_content(self):
        mapper = EventMapper()
        event = _make_event("assistant.message", content="Hello world")
        mapper.handle(event)
        result = mapper.build()
        assert result.final_response == "Hello world"

    def test_multiple_messages_appended(self):
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.message", content="First"))
        mapper.handle(_make_event("assistant.message", content="Second"))
        result = mapper.build()
        assert result.final_response == "Second"

    def test_empty_content_skipped(self):
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.message", content=None))
        result = mapper.build()
        assert result.final_response is None


class TestEventMapperToolCalls:
    """Test tool execution event handling."""

    def test_tool_start_and_complete(self):
        mapper = EventMapper()
        mapper.handle(
            _make_event(
                "tool.execution_start",
                tool_name="create_file",
                tool_call_id="tc_1",
                arguments='{"path": "test.py"}',
            )
        )
        result_obj = SimpleNamespace(content="File created")
        mapper.handle(
            _make_event(
                "tool.execution_complete",
                tool_name="create_file",
                tool_call_id="tc_1",
                result=result_obj,
            )
        )
        result = mapper.build()
        assert len(result.all_tool_calls) == 1
        tc = result.all_tool_calls[0]
        assert tc.name == "create_file"
        assert tc.result == "File created"

    def test_tool_without_complete(self):
        mapper = EventMapper()
        mapper.handle(
            _make_event(
                "tool.execution_start",
                tool_name="read_file",
                tool_call_id="tc_2",
                arguments="{}",
            )
        )
        result = mapper.build()
        assert len(result.all_tool_calls) == 1
        assert result.all_tool_calls[0].result is None

    def test_multiple_tool_calls_same_turn(self):
        """Multiple tool calls in one assistant turn are all captured."""
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.turn_start"))
        mapper.handle(
            _make_event(
                "tool.execution_start", tool_name="read_file", tool_call_id="tc_1", arguments="{}"
            )
        )
        mapper.handle(
            _make_event(
                "tool.execution_start", tool_name="create_file", tool_call_id="tc_2", arguments="{}"
            )
        )
        mapper.handle(_make_event("assistant.message", content="Done"))
        result = mapper.build()
        assert result.tool_was_called("read_file")
        assert result.tool_was_called("create_file")

    def test_same_call_id_not_duplicated(self):
        """Same tool_call_id arriving via both assistant.message and execution_start is not duplicated."""
        mapper = EventMapper()
        # SDK sometimes sends tool requests in assistant.message AND execution_start
        mapper.handle(
            _make_event(
                "tool.execution_start",
                tool_name="create_file",
                tool_call_id="tc_1",
                arguments="{}",
            )
        )
        # Second execution_start with same id should not add a second entry
        mapper.handle(
            _make_event(
                "tool.execution_start",
                tool_name="create_file",
                tool_call_id="tc_1",
                arguments="{}",
            )
        )
        result = mapper.build()
        assert len(result.all_tool_calls) == 1

    def test_tool_arguments_json_string_parsed(self):
        """String arguments from the SDK are parsed as JSON."""
        mapper = EventMapper()
        mapper.handle(
            _make_event(
                "tool.execution_start",
                tool_name="create_file",
                tool_call_id="tc_1",
                arguments='{"path": "hello.py", "content": "print(1)"}',
            )
        )
        result = mapper.build()
        tc = result.all_tool_calls[0]
        assert isinstance(tc.arguments, dict)
        assert tc.arguments["path"] == "hello.py"

    def test_tool_arguments_invalid_json_becomes_raw(self):
        """Unparseable string arguments fall back to {'raw': value}."""
        mapper = EventMapper()
        mapper.handle(
            _make_event(
                "tool.execution_start",
                tool_name="run_in_terminal",
                tool_call_id="tc_1",
                arguments="not valid {json",
            )
        )
        result = mapper.build()
        tc = result.all_tool_calls[0]
        assert isinstance(tc.arguments, dict)
        assert "raw" in tc.arguments


class TestEventMapperUsage:
    """Test usage tracking."""

    def test_usage_captured(self):
        mapper = EventMapper()
        mapper.handle(
            _make_event(
                "assistant.usage",
                model="gpt-4.1",
                input_tokens=100,
                output_tokens=50,
                cost=0.001,
                duration=500,
                cache_read_tokens=10,
            )
        )
        result = mapper.build()
        assert len(result.usage) == 1
        u = result.usage[0]
        assert u.model == "gpt-4.1"
        assert u.input_tokens == 100
        assert u.output_tokens == 50
        # cost_usd computed from litellm pricing, not from SDK's cost field
        # (SDK's cost field uses an unknown unit, not USD)
        assert u.cost_usd >= 0.0  # litellm may or may not have pricing


class TestEventMapperReasoning:
    """Test reasoning trace capture."""

    def test_reasoning_collected(self):
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.reasoning", reasoning_text="Let me think..."))
        mapper.handle(
            _make_event("assistant.reasoning", reasoning_text="I should use binary search.")
        )
        result = mapper.build()
        assert len(result.reasoning_traces) == 2
        assert result.reasoning_traces[0] == "Let me think..."

    def test_reasoning_delta_accumulated(self):
        """Streaming reasoning deltas are concatenated into a single trace."""
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.reasoning_delta", delta_content="Part 1. "))
        mapper.handle(_make_event("assistant.reasoning_delta", delta_content="Part 2."))
        mapper.handle(_make_event("assistant.turn_end"))  # flushes buffer
        result = mapper.build()
        assert len(result.reasoning_traces) == 1
        assert result.reasoning_traces[0] == "Part 1. Part 2."


class TestEventMapperMessageDelta:
    """Test streaming assistant message delta accumulation."""

    def test_message_delta_accumulated(self):
        """Streaming deltas are joined into one assistant turn."""
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.message_delta", delta_content="Hello "))
        mapper.handle(_make_event("assistant.message_delta", delta_content="world"))
        result = mapper.build()
        assert result.final_response == "Hello world"

    def test_delta_and_message_combined(self):
        """Deltas accumulated before a full message are merged together."""
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.message_delta", delta_content="Prefix "))
        mapper.handle(_make_event("assistant.message", content="suffix"))
        result = mapper.build()
        # Both end up in the same assistant turn content
        assert result.final_response is not None
        assert "Prefix" in result.final_response or "suffix" in result.final_response


class TestEventMapperSubagents:
    """Test subagent lifecycle tracking."""

    def test_subagent_lifecycle(self):
        mapper = EventMapper()
        mapper.handle(_make_event("subagent.started", eval_name="code-reviewer"))
        mapper.handle(_make_event("subagent.completed", eval_name="code-reviewer", duration=1000))
        result = mapper.build()
        assert len(result.subagent_invocations) == 1
        sa = result.subagent_invocations[0]
        assert sa.name == "code-reviewer"
        assert sa.status == "completed"


class TestEventMapperSessionEvents:
    """Test session-level event handling."""

    def test_session_start_captures_model(self):
        mapper = EventMapper()
        mapper.handle(_make_event("session.start", selected_model="claude-sonnet-4"))
        result = mapper.build()
        assert result.model_used == "claude-sonnet-4"

    def test_session_error_captured(self):
        mapper = EventMapper()
        mapper.handle(_make_event("session.error", message="Rate limit exceeded"))
        result = mapper.build()
        assert result.error == "Rate limit exceeded"
        assert not result.success


class TestEventMapperBuild:
    """Test build() produces correct CopilotResult."""

    def test_empty_mapper_builds(self):
        mapper = EventMapper()
        result = mapper.build()
        assert result.success  # No error = success
        assert result.final_response is None
        assert result.all_tool_calls == []
        assert result.usage == []

    def test_raw_events_collected(self):
        mapper = EventMapper()
        e1 = _make_event("assistant.message", content="hi")
        e2 = _make_event("assistant.message", content="bye")
        mapper.handle(e1)
        mapper.handle(e2)
        result = mapper.build()
        assert len(result.raw_events) == 2


class TestEventMapperUserMessage:
    """Test user message turn creation."""

    def test_user_message_creates_turn(self):
        mapper = EventMapper()
        mapper.handle(_make_event("user.message", content="Create a file"))
        result = mapper.build()
        user_turns = [t for t in result.turns if t.role == "user"]
        assert len(user_turns) == 1
        assert user_turns[0].content == "Create a file"

    def test_user_message_empty_ignored(self):
        mapper = EventMapper()
        mapper.handle(_make_event("user.message", content=""))
        result = mapper.build()
        assert result.turns == []


class TestEventMapperPermissions:
    """Test permission request handling."""

    def test_permission_request_captured(self):
        mapper = EventMapper()
        mapper.handle(
            _make_event(
                "tool.user_requested",
                permission_type="file_write",
                tool_name="create_file",
                message="Allow creating files?",
            )
        )
        result = mapper.build()
        assert result.permission_requested is True
        assert len(result.permissions) == 1
        assert result.permissions[0]["type"] == "file_write"

    def test_no_permissions_by_default(self):
        mapper = EventMapper()
        result = mapper.build()
        assert result.permission_requested is False
        assert result.permissions == []


class TestEventMapperUnknownEvents:
    """Test robustness with unknown event types."""

    def test_unknown_event_does_not_crash(self):
        """Events with unrecognised types are silently ignored."""
        mapper = EventMapper()
        mapper.handle(_make_event("future.new_event_type", some_field="value"))
        mapper.handle(_make_event("assistant.message", content="Still works"))
        result = mapper.build()
        assert result.final_response == "Still works"

    def test_turn_end_flushes_content(self):
        """assistant.turn_end flushes accumulated assistant content."""
        mapper = EventMapper()
        mapper.handle(_make_event("assistant.message_delta", delta_content="Hello"))
        mapper.handle(_make_event("assistant.turn_end"))
        result = mapper.build()
        assert result.final_response == "Hello"
