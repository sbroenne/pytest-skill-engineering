"""SDK event and result property tests.

Verifies that Copilot-specific result properties are correctly populated
from the SDK event stream. These test the plugin's integration with the
SDK itself, not agent behavior.

Covered properties:
    result.reasoning_traces     — reasoning effort configuration works
    result.usage                — token counts and cost are captured
    result.token_usage          — pytest-aitest compatible dict format
    result.raw_events           — full event stream captured for debugging
    result.model_used           — model selection is reflected in result
"""

from __future__ import annotations

import pytest

from pytest_aitest.copilot.agent import CopilotAgent


@pytest.mark.copilot
class TestReasoningEffort:
    """reasoning_effort configuration is accepted and run succeeds."""

    async def test_reasoning_effort_high_does_not_break_run(self, copilot_run, tmp_path):
        """Agent configured with reasoning_effort='high' completes successfully.

        Reasoning traces are model-dependent — not all models emit them.
        This test verifies the configuration is accepted and the run
        produces a valid result. The reasoning_traces list may be empty.
        """
        agent = CopilotAgent(
            name="high-reasoning",
            reasoning_effort="high",
            instructions="Think carefully before coding.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
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

    async def test_usage_info_captured(self, copilot_run, tmp_path):
        """Usage info (tokens, cost) is populated from assistant.usage events."""
        agent = CopilotAgent(
            name="usage-tracker",
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create echo.py that prints its sys.argv arguments.")
        assert result.success
        assert len(result.usage) > 0, "Expected at least one UsageInfo entry"
        assert result.usage[0].input_tokens > 0 or result.usage[0].output_tokens > 0, (
            "Expected non-zero token counts in usage"
        )

    async def test_token_usage_dict_is_aitest_compatible(self, copilot_run, tmp_path):
        """token_usage property returns a pytest-aitest compatible dict.

        pytest-aitest reads prompt/completion/total keys from this dict
        for its AI analysis report. The keys must match exactly.
        """
        agent = CopilotAgent(
            name="token-dict",
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create hi.py with print('hi')")
        assert result.success
        usage = result.token_usage
        assert set(usage.keys()) >= {"prompt", "completion", "total"}, (
            f"token_usage missing required keys. Got: {set(usage.keys())}"
        )
        assert usage["total"] == usage["prompt"] + usage["completion"]

    async def test_total_cost_is_non_negative(self, copilot_run, tmp_path):
        """Cost tracking produces a non-negative value."""
        agent = CopilotAgent(
            name="cost-check",
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create hello.py with print('hello')")
        assert result.success
        assert result.total_cost_usd >= 0.0

    async def test_model_used_captured(self, copilot_run, tmp_path):
        """model_used is populated from the SDK session or usage events."""
        agent = CopilotAgent(
            name="model-check",
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create hi.py with print('hi')")
        assert result.success
        # model_used may be None if session.start event didn't fire,
        # but when populated it must be a non-empty string
        if result.model_used is not None:
            assert len(result.model_used) > 0


@pytest.mark.copilot
class TestEventCapture:
    """Raw events and result metadata are captured for debugging and reporting."""

    async def test_raw_events_populated(self, copilot_run, tmp_path):
        """raw_events captures the full SDK event stream."""
        agent = CopilotAgent(
            name="event-capture",
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create note.txt with 'test note'")
        assert result.success
        assert len(result.raw_events) > 0, "Expected raw events to be captured"

    async def test_all_tool_calls_captured(self, copilot_run, tmp_path):
        """Tool calls are captured in result.all_tool_calls."""
        agent = CopilotAgent(
            name="tool-capture",
            instructions="Create files as requested.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create hello.py with print('hello')")
        assert result.success
        assert len(result.all_tool_calls) > 0, "Expected at least one tool call captured"
        for tc in result.all_tool_calls:
            assert tc.name, "ToolCall.name must not be empty"
            assert isinstance(tc.arguments, dict), "ToolCall.arguments must be a dict"
