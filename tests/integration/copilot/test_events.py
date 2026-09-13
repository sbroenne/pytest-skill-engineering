"""SDK event and result property tests.

Verifies that Copilot-specific result properties are correctly populated
from the SDK event stream. These test the plugin's integration with the
SDK itself, not agent behavior.

Covered properties:
    result.reasoning_traces     — reasoning effort configuration works
    result.usage                — token counts and cost are captured
    result.token_usage          — pytest-skill-engineering compatible dict format
    result.raw_events           — full event stream captured for debugging
    result.model_used           — model selection is reflected in result
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

from .conftest import DEFAULT_MODEL


@pytest.mark.copilot
class TestReasoningEffort:
    """reasoning_effort configuration is accepted and run succeeds."""

    async def test_reasoning_effort_high_does_not_break_run(self, copilot_eval, tmp_path):
        """Eval configured with reasoning_effort='high' completes successfully.

        Reasoning traces are model-dependent — not all models emit them.
        This test verifies the configuration is accepted and the run
        produces a valid result. The reasoning_traces list may be empty.
        """
        agent = CopilotEval(
            name="high-reasoning",
            model=DEFAULT_MODEL,
            reasoning_effort="high",
            instructions="Think carefully before coding.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create search.py with a binary_search(arr, target) function.",
        )
        assert result.success, f"reasoning_effort='high' run failed: {result.error}"
        assert (tmp_path / "search.py").exists()
        # reasoning_traces may be empty (model-dependent) but must be a list
        assert isinstance(result.reasoning_traces, list)


@pytest.mark.copilot
class TestUsageTracking:
    """Token usage and cost are captured from SDK events."""

    async def test_usage_info_captured(self, copilot_eval, tmp_path):
        """Usage info (tokens, cost) is populated from assistant.usage events."""
        agent = CopilotEval(
            name="usage-tracker",
            model=DEFAULT_MODEL,
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(agent, "Create echo.py that prints its sys.argv arguments.")
        assert result.success
        assert len(result.usage) > 0, "Expected at least one UsageInfo entry"
        assert result.usage[0].input_tokens > 0 or result.usage[0].output_tokens > 0, (
            "Expected non-zero token counts in usage"
        )

    async def test_token_usage_dict_is_aitest_compatible(self, copilot_eval, tmp_path):
        """token_usage property returns a pytest-skill-engineering compatible dict.

        pytest-skill-engineering reads prompt/completion/total keys from this dict
        for its AI analysis report. The keys must match exactly.
        """
        agent = CopilotEval(
            name="token-dict",
            model=DEFAULT_MODEL,
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(agent, "Create hi.py with print('hi')")
        assert result.success
        usage = result.token_usage
        assert set(usage.keys()) >= {"prompt", "completion", "total"}, (
            f"token_usage missing required keys. Got: {set(usage.keys())}"
        )
        assert usage["total"] == usage["prompt"] + usage["completion"]

    async def test_premium_requests_match_sdk_events(self, copilot_eval, tmp_path, record_property):
        """Premium request totals must come from actual SDK shutdown events."""
        agent = CopilotEval(
            name="cost-check",
            model=DEFAULT_MODEL,
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(agent, "Create hello.py with print('hello')")
        assert result.success
        shutdown_events = [
            event for event in result.raw_events if event.type.value == "session.shutdown"
        ]
        record_property("shutdown_events_seen", len(shutdown_events))
        if shutdown_events:
            reported = shutdown_events[-1].data._total_premium_requests
            assert result.total_premium_requests == float(reported or 0)
        else:
            assert result.total_premium_requests == 0.0

    async def test_model_used_captured(self, copilot_eval, tmp_path):
        """model_used is populated from the SDK session or usage events."""
        agent = CopilotEval(
            name="model-check",
            model=DEFAULT_MODEL,
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(agent, "Create hi.py with print('hi')")
        assert result.success
        assert result.model_used, "Expected model metadata from the session event stream"


@pytest.mark.copilot
class TestEventCapture:
    """Raw events and result metadata are captured for debugging and reporting."""

    async def test_raw_events_populated(self, copilot_eval, tmp_path):
        """raw_events captures the full SDK event stream."""
        agent = CopilotEval(
            name="event-capture",
            model=DEFAULT_MODEL,
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(agent, "Create note.txt with 'test note'")
        assert result.success
        assert len(result.raw_events) > 0, "Expected raw events to be captured"
        event_types = {event.type.value for event in result.raw_events}
        assert "session.start" in event_types, "Session creation events must not be lost"
        event_ids = [event.id for event in result.raw_events]
        assert len(event_ids) == len(set(event_ids)), "Events must be recorded exactly once"

    async def test_all_tool_calls_captured(self, copilot_eval, tmp_path):
        """Tool calls are captured in result.all_tool_calls."""
        agent = CopilotEval(
            name="tool-capture",
            model=DEFAULT_MODEL,
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(agent, "Create hello.py with print('hello')")
        assert result.success
        assert len(result.all_tool_calls) > 0, "Expected at least one tool call captured"
        for tc in result.all_tool_calls:
            assert tc.name, "ToolCall.name must not be empty"
            assert isinstance(tc.arguments, dict), "ToolCall.arguments must be a dict"
