"""Fixtures for integration tests.

Centralized configuration and server fixtures for all integration tests.
Tests should import constants from here and create agents inline.

Example:
    from tests.integration.conftest import (
        DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM, DEFAULT_MAX_TURNS,
        BENCHMARK_MODELS, BANKING_PROMPT, TODO_PROMPT,
    )

    @pytest.mark.asyncio
    async def test_banking(eval_run, banking_server):
        agent = Eval(
            name="banking-test",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            system_prompt=BANKING_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )
        result = await eval_run(agent, "What's my checking balance?")
        assert result.success
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Load .env from workspace root
_env_file = Path(__file__).parents[4] / ".env"
if _env_file.exists():
    from dotenv import load_dotenv

    load_dotenv(_env_file)

# LiteLLM bug workaround: Azure SDK uses AZURE_OPENAI_ENDPOINT but
# PydanticAI adapter reads AZURE_API_BASE. Set both for compatibility.
if os.environ.get("AZURE_OPENAI_ENDPOINT") and not os.environ.get("AZURE_API_BASE"):
    os.environ["AZURE_API_BASE"] = os.environ["AZURE_OPENAI_ENDPOINT"]

from pytest_skill_engineering import MCPServer, Wait

# =============================================================================
# Pytest Configuration Hooks
# =============================================================================


# =============================================================================
# Test Configuration Constants
# =============================================================================

# Default model for most tests (cheapest Azure deployment)
DEFAULT_MODEL = "gpt-5-mini"

# Models for benchmark comparison (cheap vs capable)
BENCHMARK_MODELS = ["gpt-5-mini", "gpt-4.1-mini"]

# Rate limits for Azure deployments
DEFAULT_RPM = 10
DEFAULT_TPM = 10000

# Default turn limits
DEFAULT_MAX_TURNS = 5

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

# =============================================================================
# MCP Server Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def todo_server():
    """Todo MCP server - stateful task management."""
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_skill_engineering.testing.todo_mcp",
        ],
        wait=Wait.for_tools(["add_task", "list_tasks", "complete_task"]),
    )


@pytest.fixture(scope="module")
def banking_server():
    """Banking MCP server - realistic banking scenario.

    Provides:
    - 2 accounts: checking ($1,500), savings ($3,000)
    - Tools: get_balance, get_all_balances, transfer, deposit, withdraw, get_transactions
    """
    return MCPServer(
        command=[
            sys.executable,
            "-u",
            "-m",
            "pytest_skill_engineering.testing.banking_mcp",
        ],
        wait=Wait.for_tools(
            [
                "get_balance",
                "get_all_balances",
                "transfer",
                "deposit",
                "withdraw",
                "get_transactions",
            ]
        ),
    )
