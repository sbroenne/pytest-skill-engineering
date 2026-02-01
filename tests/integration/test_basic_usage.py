"""Basic usage tests - multi-step workflows with MCP tools.

These tests demonstrate realistic agent workflows that require multiple tool calls,
reasoning between steps, and validation of end-to-end behavior.

Run with: pytest tests/integration/test_basic_usage.py -v
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.basic]


# =============================================================================
# Weather Server - Multi-step Workflows
# =============================================================================


class TestWeatherWorkflows:
    """Multi-step weather workflows that test real-world usage patterns."""

    @pytest.mark.asyncio
    async def test_trip_planning_compare_destinations(
        self, aitest_run, weather_agent_factory, judge
    ):
        """Plan a trip: get forecasts for two cities and recommend the better one.

        This tests:
        - Multiple forecast calls (one per city)
        - Reasoning across retrieved data
        - Synthesizing a recommendation
        - AI judge for semantic validation
        """
        agent = weather_agent_factory("gpt-5-mini", max_turns=10)

        result = await aitest_run(
            agent,
            "I'm planning a trip next week and can't decide between Paris and Sydney. "
            "Get me a 3-day forecast for both cities and recommend which has better "
            "weather for sightseeing. I prefer sunny weather.",
        )

        assert result.success
        # Should get forecasts for both cities
        assert result.tool_call_count("get_forecast") >= 2
        # Should synthesize an answer mentioning both cities
        response_lower = result.final_response.lower()
        assert "paris" in response_lower
        assert "sydney" in response_lower
        # AI judge validates recommendation quality
        assert judge(
            result.final_response,
            """
            - Compares weather between two cities
            - Makes a recommendation for one destination
            - Justifies the choice based on weather data
        """,
        )

    @pytest.mark.asyncio
    async def test_packing_advice_workflow(self, aitest_run, weather_agent_factory):
        """Check multiple cities and provide packing advice.

        This tests:
        - Gathering data from multiple sources
        - Conditional reasoning (rain → umbrella)
        - Practical advice generation
        """
        agent = weather_agent_factory("gpt-5-mini", max_turns=10)

        result = await aitest_run(
            agent,
            "I'm traveling to London and Berlin this week. Check the weather in both "
            "cities and tell me if I should pack an umbrella or rain jacket.",
        )

        assert result.success
        # Should check weather for both cities
        weather_calls = result.tool_call_count("get_weather")
        compare_calls = result.tool_call_count("compare_weather")
        assert weather_calls >= 2 or compare_calls >= 1
        # London has "Rainy" conditions, should mention umbrella
        response_lower = result.final_response.lower()
        assert "london" in response_lower
        assert any(word in response_lower for word in ["umbrella", "rain", "wet"])

    @pytest.mark.asyncio
    async def test_discovery_then_query_workflow(self, aitest_run, weather_agent_factory):
        """Discover available cities, then query the warmest one.

        This tests:
        - Discovery phase (list available resources)
        - Decision making based on discovered data
        - Follow-up action based on analysis
        """
        agent = weather_agent_factory("gpt-5-mini", max_turns=15)

        result = await aitest_run(
            agent,
            "What cities can you get weather for? Then find the warmest one and "
            "give me its 5-day forecast.",
        )

        assert result.success
        # Should discover cities first
        assert result.tool_was_called("list_cities")
        # Should then get weather for multiple cities to compare
        assert result.tool_was_called("get_weather") or result.tool_was_called("get_forecast")
        # Sydney is warmest (26°C) - should mention it
        assert "sydney" in result.final_response.lower()

    @pytest.mark.asyncio
    async def test_comparative_analysis_three_cities(self, aitest_run, weather_agent_factory):
        """Compare weather across three cities and rank them.

        This tests:
        - Multiple tool calls (3+ cities)
        - Comparative reasoning
        - Structured output (ranking)
        """
        agent = weather_agent_factory("gpt-5-mini", max_turns=12)

        result = await aitest_run(
            agent,
            "Compare the current weather in Tokyo, Berlin, and New York. "
            "Rank them from warmest to coldest and explain the conditions.",
        )

        assert result.success
        # Should gather data for all three cities
        total_calls = result.tool_call_count("get_weather") + result.tool_call_count(
            "compare_weather"
        )
        assert total_calls >= 2  # At minimum, needs data from 3 cities
        # Response should mention all three cities
        response_lower = result.final_response.lower()
        assert "tokyo" in response_lower
        assert "berlin" in response_lower
        assert "new york" in response_lower

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, aitest_run, weather_agent_factory):
        """Handle an invalid city gracefully and provide alternatives.

        This tests:
        - Error handling from tool
        - Recovery behavior (suggest alternatives)
        - Graceful degradation
        """
        agent = weather_agent_factory("gpt-5-mini", max_turns=8)

        result = await aitest_run(
            agent,
            "Get me the weather for Atlantis. If that city isn't available, "
            "list what cities you do support and give me weather for the first one.",
        )

        assert result.success
        # Should try the invalid city first
        assert result.tool_was_called("get_weather")
        # Should recover by listing cities or getting a valid city's weather
        assert result.tool_was_called("list_cities") or result.tool_call_count("get_weather") >= 2


# =============================================================================
# Todo Server - Multi-step Workflows
# =============================================================================


class TestTodoWorkflows:
    """Multi-step task management workflows that test stateful operations."""

    @pytest.mark.asyncio
    async def test_project_setup_workflow(self, aitest_run, todo_agent_factory):
        """Create multiple tasks and verify the list.

        This tests:
        - Multiple sequential writes
        - State persistence between calls
        - Verification via read
        """
        agent = todo_agent_factory("gpt-5-mini", max_turns=12)

        result = await aitest_run(
            agent,
            "Set up my groceries list: add milk, bread, and eggs. "
            "Then show me the complete list to confirm everything was added.",
        )

        assert result.success
        # Should add all three items
        assert result.tool_call_count("add_task") >= 3
        # Should verify with list
        assert result.tool_was_called("list_tasks")
        # Final response should confirm all items
        response_lower = result.final_response.lower()
        assert "milk" in response_lower
        assert "bread" in response_lower
        assert "eggs" in response_lower

    @pytest.mark.asyncio
    async def test_task_lifecycle_workflow(self, aitest_run, todo_agent_factory, judge):
        """Full task lifecycle: create, complete, verify.

        This tests:
        - Create → state change → verify pattern
        - ID tracking between operations
        - State verification after mutations
        - AI judge for semantic validation
        """
        agent = todo_agent_factory("gpt-5-mini", max_turns=10)

        result = await aitest_run(
            agent,
            "Add 'review quarterly report' to my work list. "
            "Then mark it as complete. "
            "Finally show my work list to confirm it's marked done.",
        )

        assert result.success
        # Full lifecycle: add → complete → verify
        assert result.tool_was_called("add_task")
        assert result.tool_was_called("complete_task")
        assert result.tool_was_called("list_tasks")
        # AI judge validates the workflow report
        assert judge(
            result.final_response,
            """
            - Confirms task was added
            - Indicates task was marked complete
            - Shows or describes the final list state
        """,
        )

    @pytest.mark.asyncio
    async def test_priority_management_workflow(self, aitest_run, todo_agent_factory):
        """Create tasks with different priorities and query by priority.

        This tests:
        - Parameter usage (priority field)
        - Querying/filtering results
        - Understanding of priority semantics
        """
        agent = todo_agent_factory("gpt-5-mini", max_turns=12)

        result = await aitest_run(
            agent,
            "Create three tasks in my work list:\n"
            "1. 'Fix critical bug' with HIGH priority\n"
            "2. 'Update documentation' with LOW priority\n"
            "3. 'Review PR' with NORMAL priority\n\n"
            "Then show me all tasks and tell me which one I should do first.",
        )

        assert result.success
        # Should create all three tasks
        assert result.tool_call_count("add_task") >= 3
        # Should list tasks
        assert result.tool_was_called("list_tasks")
        # Should recommend the high priority task first
        response_lower = result.final_response.lower()
        assert "critical bug" in response_lower or "high" in response_lower
        assert any(word in response_lower for word in ["first", "priority", "urgent"])

    @pytest.mark.asyncio
    async def test_batch_completion_workflow(self, aitest_run, todo_agent_factory):
        """Add tasks, complete multiple, then show remaining.

        This tests:
        - Batch operations (completing multiple)
        - State tracking across operations
        - Filtering (remaining vs completed)
        """
        agent = todo_agent_factory("gpt-5-mini", max_turns=15)

        result = await aitest_run(
            agent,
            "Add these tasks to my quick-tasks list: 'send email', 'make call', 'write note'. "
            "Then mark 'send email' and 'make call' as complete. "
            "Finally show me only the remaining incomplete tasks.",
        )

        assert result.success
        # Should add multiple tasks
        assert result.tool_call_count("add_task") >= 3
        # Should complete multiple
        assert result.tool_call_count("complete_task") >= 2
        # Should list remaining
        assert result.tool_was_called("list_tasks")
        # The only incomplete task should be "write note"
        response_lower = result.final_response.lower()
        assert "write note" in response_lower or "note" in response_lower

    @pytest.mark.asyncio
    async def test_multi_list_organization(self, aitest_run, todo_agent_factory):
        """Organize tasks across multiple lists.

        This tests:
        - Working with multiple lists/namespaces
        - Understanding list semantics
        - Cross-list queries
        """
        agent = todo_agent_factory("gpt-5-mini", max_turns=12)

        result = await aitest_run(
            agent,
            "Add 'buy groceries' to my personal list and 'submit report' to my work list. "
            "Then tell me what lists I have and how many tasks are in each.",
        )

        assert result.success
        # Should add tasks to different lists
        assert result.tool_call_count("add_task") >= 2
        # Should query lists
        assert result.tool_was_called("get_lists") or result.tool_was_called("list_tasks")
        # Should mention both lists in response
        response_lower = result.final_response.lower()
        assert "personal" in response_lower
        assert "work" in response_lower


# =============================================================================
# Advanced Patterns
# =============================================================================


class TestAdvancedPatterns:
    """Tests for more complex agent behaviors."""

    @pytest.mark.asyncio
    async def test_ambiguous_request_clarification(self, aitest_run, weather_agent_factory):
        """Handle ambiguous requests intelligently.

        This tests:
        - Interpretation of vague requests
        - Intelligent defaults or clarification
        - Graceful handling of underspecified input
        """
        agent = weather_agent_factory("gpt-5-mini", max_turns=8)

        result = await aitest_run(
            agent,
            "What's the weather like in Europe?",
        )

        assert result.success
        # Agent should either:
        # 1. Pick European cities and report on them, or
        # 2. Ask for clarification, or
        # 3. List available European cities
        response_lower = result.final_response.lower()
        # Should mention at least one European city (Paris, Berlin, London)
        assert any(city in response_lower for city in ["paris", "berlin", "london"])

    @pytest.mark.asyncio
    async def test_conditional_logic_workflow(self, aitest_run, todo_agent_factory):
        """Execute conditional logic based on current state.

        This tests:
        - Check-then-act pattern
        - Conditional branching based on data
        - State-aware decision making
        """
        agent = todo_agent_factory("gpt-5-mini", max_turns=10)

        result = await aitest_run(
            agent,
            "Check if I have any tasks in my 'urgent' list. "
            "If not, create one called 'check email' with high priority. "
            "Show me the urgent list either way.",
        )

        assert result.success
        # Should check the list first
        assert result.tool_was_called("list_tasks") or result.tool_was_called("get_lists")
        # Should create the task (since urgent list is empty initially)
        assert result.tool_was_called("add_task")
        # Should verify
        assert result.tool_call_count("list_tasks") >= 1
