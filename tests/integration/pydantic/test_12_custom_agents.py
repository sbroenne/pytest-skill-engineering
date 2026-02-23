"""Level 12 — Custom agents: test Eval.from_agent_file() and load_custom_agent().

Tests that .agent.md files are correctly parsed and produce working evals.
Frontmatter (description, tools) is mapped to agent identity and allowed_tools.

Permutation: Custom agent file as eval source.

Run with: pytest tests/integration/pydantic/test_12_custom_agents.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, Provider, load_custom_agent, load_custom_agents

from ..conftest import (
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration]

AGENTS_DIR = Path(__file__).parents[1] / "agents"


# =============================================================================
# Loading and Parsing
# =============================================================================


class TestCustomAgentLoading:
    """Custom agent files are correctly parsed and loaded."""

    def test_load_custom_agent_with_frontmatter(self):
        """load_custom_agent parses frontmatter metadata and body prompt."""
        agent = load_custom_agent(AGENTS_DIR / "banking-advisor.agent.md")

        assert agent["name"] == "banking-advisor"
        assert agent["description"] == "Banking advisor that checks balances and performs transfers"
        assert "banking advisor" in agent["prompt"].lower()
        assert agent["metadata"]["tools"] == ["get_balance", "get_all_balances", "transfer"]

    def test_load_custom_agent_without_frontmatter(self):
        """load_custom_agent handles files with no YAML frontmatter."""
        agent = load_custom_agent(AGENTS_DIR / "minimal.agent.md")

        assert agent["name"] == "minimal"
        assert agent["description"] == ""
        assert agent["metadata"].get("tools") is None
        assert "helpful assistant" in agent["prompt"].lower()

    def test_load_custom_agents_directory(self):
        """load_custom_agents loads all .agent.md files from a directory."""
        agents = load_custom_agents(AGENTS_DIR)

        names = {a["name"] for a in agents}
        assert "banking-advisor" in names
        assert "todo-manager" in names
        assert "minimal" in names
        assert len(agents) >= 3

    def test_load_custom_agents_with_include_filter(self):
        """load_custom_agents include filter limits which agents are loaded."""
        agents = load_custom_agents(AGENTS_DIR, include={"banking-advisor"})

        assert len(agents) == 1
        assert agents[0]["name"] == "banking-advisor"

    def test_load_custom_agents_with_exclude_filter(self):
        """load_custom_agents exclude filter skips specified agents."""
        agents = load_custom_agents(AGENTS_DIR, exclude={"minimal"})

        names = {a["name"] for a in agents}
        assert "minimal" not in names
        assert "banking-advisor" in names

    def test_load_custom_agent_nonexistent_raises(self):
        """load_custom_agent raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            load_custom_agent(AGENTS_DIR / "nonexistent.agent.md")


# =============================================================================
# Eval.from_agent_file — Synthetic Agent Testing
# =============================================================================


class TestFromAgentFile:
    """Eval.from_agent_file() creates working evals from .agent.md files."""

    async def test_banking_agent_balance_check(self, eval_run, banking_server):
        """Banking advisor agent file produces a working eval that checks balances."""
        agent = Eval.from_agent_file(
            AGENTS_DIR / "banking-advisor.agent.md",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")

    async def test_banking_agent_transfer(self, eval_run, banking_server):
        """Banking advisor agent file handles transfer requests."""
        agent = Eval.from_agent_file(
            AGENTS_DIR / "banking-advisor.agent.md",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "Transfer $100 from checking to savings.")

        assert result.success
        assert result.tool_was_called("transfer")

    async def test_todo_agent_add_task(self, eval_run, todo_server):
        """Todo manager agent file produces a working eval that adds tasks."""
        agent = Eval.from_agent_file(
            AGENTS_DIR / "todo-manager.agent.md",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[todo_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "Add a task: Buy groceries.")

        assert result.success
        assert result.tool_was_called("add_task")

    async def test_minimal_agent_with_banking_tools(self, eval_run, banking_server):
        """Minimal agent file (no frontmatter) works with explicit MCP servers."""
        agent = Eval.from_agent_file(
            AGENTS_DIR / "minimal.agent.md",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(agent, "Show me all my account balances.")

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")


# =============================================================================
# Agent Identity in Results
# =============================================================================


class TestAgentIdentity:
    """Eval created from agent file carries agent identity metadata."""

    async def test_custom_agent_name_in_result(self, eval_run, banking_server):
        """Result captures custom_agent_name from the agent file."""
        agent = Eval.from_agent_file(
            AGENTS_DIR / "banking-advisor.agent.md",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            mcp_servers=[banking_server],
            max_turns=DEFAULT_MAX_TURNS,
        )

        assert agent.custom_agent_name == "banking-advisor"
        assert (
            agent.custom_agent_description
            == "Banking advisor that checks balances and performs transfers"
        )

        result = await eval_run(agent, "What's my checking balance?")
        assert result.success
