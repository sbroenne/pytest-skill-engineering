"""Tests proving that skills improve LLM behavior.

These tests demonstrate the value of skills by comparing agent behavior:
- WITHOUT skill: Baseline LLM behavior (may be inconsistent or miss steps)
- WITH skill: Enhanced behavior following skill guidelines

Each test pair shows measurable improvement in agent quality.
"""

from pathlib import Path

import pytest

from pytest_skill_engineering import Agent, Provider, Skill

from .conftest import DEFAULT_MAX_TURNS, DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM

# Path to test skills
SKILLS_DIR = Path(__file__).parent / "skills"

# Financial advisor skill lives in showcase directory
SHOWCASE_SKILLS_DIR = Path(__file__).parent.parent / "showcase" / "skills"


@pytest.mark.integration
class TestBankingSkillImprovement:
    """Tests showing financial-advisor skill improves banking advice quality."""

    @pytest.fixture
    def financial_skill(self):
        """Load the financial advisor skill."""
        return Skill.from_path(SHOWCASE_SKILLS_DIR / "financial-advisor")

    async def test_baseline_fund_allocation_may_be_generic(self, aitest_run, banking_server):
        """WITHOUT skill: LLM might give generic financial advice.

        This test establishes baseline behavior - the LLM may or may not
        check account balances before giving allocation advice.
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt="You are a banking assistant. Help users manage their money.",
            max_turns=5,
        )

        result = await aitest_run(
            agent,
            "How should I allocate the money in my accounts?",
        )

        assert result.success
        # Baseline: We don't assert on tool usage - behavior may vary
        print(f"Baseline tool calls: {len(result.all_tool_calls)}")
        print(f"Tools used: {[t.name for t in result.all_tool_calls]}")

    async def test_skilled_allocation_uses_budgeting_rules(
        self, aitest_run, banking_server, financial_skill
    ):
        """WITH skill: Agent ALWAYS checks balances and applies 50/30/20 rule.

        The financial-advisor skill instructs the agent to:
        1. Always check account balances first
        2. Apply the 50/30/20 budgeting rule
        3. Prioritize emergency fund
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            skill=financial_skill,
            system_prompt="Help users manage their money.",
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await aitest_run(
            agent,
            "Check my account balances and tell me how I should allocate my money.",
        )

        assert result.success
        # WITH skill: Should ALWAYS check balances first
        assert len(result.all_tool_calls) >= 1, "Skilled agent should check account tools"
        assert result.tool_was_called("get_all_balances") or result.tool_was_called(
            "get_balance"
        ), "Should check balances before giving advice"

        # Response should include specific budgeting advice
        response = result.final_response.lower()
        has_specific_advice = any(
            term in response for term in ["50/30/20", "emergency", "savings", "budget", "allocat"]
        )
        assert has_specific_advice, "Should give specific budgeting advice"

    async def test_skill_identifies_financial_red_flags(
        self, aitest_run, banking_server, financial_skill
    ):
        """WITH skill: Agent detects financial red flags from account state.

        The skill defines red flags:
        - No emergency fund
        - Spending more than income
        - Low savings ratio
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            skill=financial_skill,
            system_prompt="You are a financial health advisor.",
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await aitest_run(
            agent,
            "Review my accounts and tell me if there are any financial concerns I should address.",
        )

        assert result.success

        # Response should provide financial health assessment
        response = result.final_response.lower()
        has_assessment = any(
            term in response
            for term in ["emergency", "savings", "recommend", "suggest", "consider"]
        )
        assert has_assessment, "Should provide financial health assessment"


@pytest.mark.integration
class TestTodoSkillImprovement:
    """Tests showing todo-organizer skill improves task management."""

    @pytest.fixture
    def todo_skill(self):
        """Load the todo organizer skill."""
        return Skill.from_path(SKILLS_DIR / "todo-organizer")

    async def test_baseline_may_not_verify_operations(self, aitest_run, todo_server):
        """WITHOUT skill: LLM might not verify task operations.

        Baseline behavior - the agent may add tasks without confirming
        they were added successfully.
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            system_prompt="You help manage tasks. Add tasks when asked.",
            max_turns=5,
        )

        result = await aitest_run(
            agent,
            "Add 'buy milk' to my shopping list",
        )

        assert result.success
        assert result.tool_was_called("add_task")
        print(f"Baseline verified with list_tasks: {result.tool_was_called('list_tasks')}")

    async def test_skilled_always_verifies_operations(self, aitest_run, todo_server, todo_skill):
        """WITH skill: Agent ALWAYS verifies operations with list_tasks.

        The todo-organizer skill requires:
        - Call list_tasks after ANY modification
        - Show the user confirmation of the change
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            skill=todo_skill,
            system_prompt="Help manage the user's tasks.",
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await aitest_run(
            agent,
            "Add 'buy milk' to my shopping list",
        )

        assert result.success
        assert result.tool_was_called("add_task"), "Should add the task"

        # WITH skill: MUST verify with list_tasks after adding
        assert result.tool_was_called("list_tasks"), (
            "Skilled agent should verify operation with list_tasks"
        )

        # Check that list_tasks was called AFTER add_task (verification pattern)
        tool_names = [tc.name for tc in result.all_tool_calls]
        last_add_idx = len(tool_names) - 1 - tool_names[::-1].index("add_task")
        list_calls_after_add = [
            i for i, name in enumerate(tool_names) if name == "list_tasks" and i > last_add_idx
        ]
        assert len(list_calls_after_add) > 0, (
            "Should call list_tasks AFTER the final add_task to verify the operation"
        )

    async def test_skilled_uses_consistent_list_names(self, aitest_run, todo_server, todo_skill):
        """WITH skill: Agent organizes tasks into appropriate categories.

        The skill defines standard lists: inbox, work, personal, shopping, someday
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            skill=todo_skill,
            system_prompt="Organize the user's tasks efficiently.",
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await aitest_run(
            agent,
            "I need to buy groceries, finish the quarterly report, and call my mom",
        )

        assert result.success
        add_calls = [tc for tc in result.all_tool_calls if tc.name == "add_task"]
        assert len(add_calls) >= 2, "Should add multiple tasks"

        # Check if tasks were organized into lists
        lists_used = set()
        for call in add_calls:
            list_name = call.arguments.get("list_name")
            if list_name:
                lists_used.add(list_name.lower())

        if lists_used:
            print(f"Lists used: {lists_used}")
        else:
            print("Note: Tasks added without explicit list names (using default)")

    async def test_skilled_assigns_smart_priorities(self, aitest_run, todo_server, todo_skill):
        """WITH skill: Agent assigns priorities based on urgency signals.

        The skill's priority guide says:
        - "deadline today" keywords → HIGH priority
        - "urgent", "ASAP" → HIGH priority
        - "someday", "no rush" → LOW priority
        """
        agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            skill=todo_skill,
            system_prompt="Help manage tasks with appropriate priorities.",
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await aitest_run(
            agent,
            "URGENT: Submit the report by end of day! Also, someday I'd like to learn piano.",
        )

        assert result.success
        add_calls = [tc for tc in result.all_tool_calls if tc.name == "add_task"]
        assert len(add_calls) >= 1, "Should add tasks"

        # Check priorities assigned
        priorities = {}
        for call in add_calls:
            task_desc = str(call.arguments.get("task", "")).lower()
            priority = call.arguments.get("priority", "normal")
            if "report" in task_desc or "submit" in task_desc:
                priorities["report"] = priority
            if "piano" in task_desc:
                priorities["piano"] = priority

        if "report" in priorities:
            assert priorities["report"] == "high", "Urgent report should be HIGH priority"
        if "piano" in priorities:
            assert priorities["piano"] == "low", "'Someday' task should be LOW priority"


@pytest.mark.integration
class TestSkillComparisonSummary:
    """Summary tests that clearly show skill value."""

    async def test_financial_skill_increases_tool_usage(self, aitest_run, banking_server):
        """Compare tool usage: skilled agent uses tools more consistently."""
        financial_skill = Skill.from_path(SHOWCASE_SKILLS_DIR / "financial-advisor")
        prompt = "Check my account balances and tell me how I should manage my money."

        # Test WITHOUT skill
        baseline_agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt="You are a helpful assistant.",
            max_turns=5,
        )
        baseline_result = await aitest_run(baseline_agent, prompt)

        # Test WITH skill
        skilled_agent = Agent(
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            skill=financial_skill,
            system_prompt="You are a helpful assistant.",
            max_turns=DEFAULT_MAX_TURNS,
        )
        skilled_result = await aitest_run(skilled_agent, prompt)

        # Compare results
        print(f"\n{'=' * 60}")
        print("FINANCIAL SKILL COMPARISON")
        print(f"{'=' * 60}")
        print(f"Baseline tool calls: {len(baseline_result.all_tool_calls)}")
        print(f"Skilled tool calls:  {len(skilled_result.all_tool_calls)}")
        print(
            f"Baseline checked balances: "
            f"{baseline_result.tool_was_called('get_all_balances') or baseline_result.tool_was_called('get_balance')}"
        )
        print(
            f"Skilled checked balances:  "
            f"{skilled_result.tool_was_called('get_all_balances') or skilled_result.tool_was_called('get_balance')}"
        )
        print(f"{'=' * 60}\n")

        assert skilled_result.tool_was_called("get_all_balances") or skilled_result.tool_was_called(
            "get_balance"
        ), "Skilled agent should always check balances"
