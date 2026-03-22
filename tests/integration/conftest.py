"""Fixtures for integration tests.

Centralized configuration and server fixtures for Copilot integration tests.
Tests should import constants from here and create agents inline.

Example:
    from tests.integration.conftest import (
        DEFAULT_MAX_TURNS, BANKING_PROMPT, TODO_PROMPT,
    )

    @pytest.mark.asyncio
    async def test_banking(copilot_eval, tmp_path):
        from pytest_skill_engineering.copilot.eval import CopilotEval

        agent = CopilotEval(
            name="banking-test",
            instructions=BANKING_PROMPT,
            working_directory=str(tmp_path),
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await copilot_eval(agent, "What's my checking balance?")
        assert result.success
"""

from __future__ import annotations

# =============================================================================
# Pytest Configuration Hooks
# =============================================================================


# =============================================================================
# Test Configuration Constants
# =============================================================================

# Default turn limits
DEFAULT_MAX_TURNS = 25

# =============================================================================
# System Prompts
# =============================================================================

BANKING_PROMPT = """You are a banking assistant with access to account management tools.

IMPORTANT: Always use the available tools to manage accounts. Never guess balances or transaction details - the tools provide accurate, real-time data.

Available tools:
- get_balance: Get current balance for a specific account
- get_all_balances: See all account balances at once
- transfer: Move money between accounts
- deposit: Add money to an account
- withdraw: Take money from an account
- get_transactions: View transaction history

When asked about accounts, ALWAYS call the appropriate tool first, then respond based on the tool's output."""

TODO_PROMPT = """You are a task management assistant with access to a todo list system.

IMPORTANT: Always use the available tools to manage tasks. The tools are the only way to create, modify, or view tasks.

Available tools:
- add_task: Add a new task (with optional list name and priority)
- complete_task: Mark a task as done (requires task_id)
- list_tasks: View tasks (can filter by list or completion status)
- get_lists: See all available list names
- delete_task: Remove a task permanently
- set_priority: Change task priority (low, normal, high)

When asked to manage tasks, ALWAYS use the appropriate tools. After modifying tasks, use list_tasks to verify and show the user the current state."""

KEYVALUE_PROMPT = "You are a helpful assistant. Use the tools to complete tasks."
