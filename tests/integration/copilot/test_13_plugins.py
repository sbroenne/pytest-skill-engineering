"""Level 13 — Plugin testing via CopilotEval.

Tests plugin loading, from_claude_config(), and SDK passthroughs
for the Copilot SDK harness.

Copilot-exclusive — CopilotEval.from_plugin() maps plugin components
to SDK session config fields (custom_agents, instructions, skill_directories).

Run with: pytest tests/integration/copilot/test_13_plugins.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot]

PLUGIN_DIR = Path(__file__).parents[1] / "plugins" / "banking-plugin"
CLAUDE_DIR = Path(__file__).parents[1] / "plugins" / "claude-project"


# =============================================================================
# CopilotEval Factory Methods for Plugins
# =============================================================================


class TestCopilotPluginLoading:
    """Test CopilotEval factory methods for plugins."""

    def test_from_plugin(self):
        """CopilotEval.from_plugin() creates a valid eval config."""
        agent = CopilotEval.from_plugin(
            PLUGIN_DIR,
            model=DEFAULT_MODEL,
        )
        assert agent.name
        assert agent.custom_agents
        assert agent.instructions

    def test_from_plugin_custom_agents_populated(self):
        """CopilotEval.from_plugin() discovers agents from agents/ directory."""
        agent = CopilotEval.from_plugin(
            PLUGIN_DIR,
            model=DEFAULT_MODEL,
        )
        agent_names = [a.get("name", "") for a in agent.custom_agents]
        assert "banking-advisor" in agent_names

    def test_from_claude_config(self):
        """CopilotEval.from_claude_config() discovers Claude Code components."""
        agent = CopilotEval.from_claude_config(
            CLAUDE_DIR,
            model=DEFAULT_MODEL,
        )
        assert agent.instructions
        assert "coding assistant" in agent.instructions.lower()
        assert agent.custom_agents

    def test_from_claude_config_agents(self):
        """CopilotEval.from_claude_config() loads .claude/agents/ directory."""
        agent = CopilotEval.from_claude_config(
            CLAUDE_DIR,
            model=DEFAULT_MODEL,
        )
        agent_names = [a.get("name", "") for a in agent.custom_agents]
        assert "code-reviewer" in agent_names

    def test_from_plugin_with_overrides(self):
        """CopilotEval.from_plugin() accepts field overrides."""
        agent = CopilotEval.from_plugin(
            PLUGIN_DIR,
            model=DEFAULT_MODEL,
            max_turns=50,
            timeout_s=600.0,
        )
        assert agent.max_turns == 50
        assert agent.timeout_s == 600.0


# =============================================================================
# Active Agent Field
# =============================================================================


class TestActiveAgent:
    """Test CopilotEval active_agent for direct agent activation."""

    def test_active_agent_field(self):
        """CopilotEval supports active_agent for direct agent activation."""
        agent = CopilotEval(
            name="test-active",
            model=DEFAULT_MODEL,
            custom_agents=[{"name": "test-agent", "prompt": "You are a test agent."}],
            active_agent="test-agent",
        )
        assert agent.active_agent == "test-agent"

    def test_active_agent_default_none(self):
        """active_agent defaults to None when not specified."""
        agent = CopilotEval(
            name="test-default",
            model=DEFAULT_MODEL,
        )
        assert agent.active_agent is None


# =============================================================================
# Plugin Execution via CopilotEval
# =============================================================================


class TestCopilotPluginExecution:
    """Test running prompts against plugin-loaded CopilotEval configs."""

    async def test_plugin_eval_creates_output(self, copilot_eval, tmp_path):
        """CopilotEval.from_plugin() produces a working eval that can execute tasks."""
        agent = CopilotEval.from_plugin(
            PLUGIN_DIR,
            model=DEFAULT_MODEL,
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a file called balances.txt that lists checking and savings account types.",
        )
        assert result.success, f"Failed: {result.error}"
        assert list(tmp_path.rglob("balances.txt")), "balances.txt was not created"

    async def test_claude_project_eval_runs(self, copilot_eval, tmp_path):
        """CopilotEval.from_claude_config() produces a working eval."""
        agent = CopilotEval.from_claude_config(
            CLAUDE_DIR,
            model=DEFAULT_MODEL,
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a Python file called greet.py with a greet(name: str) -> str function.",
        )
        assert result.success, f"Failed: {result.error}"
        assert list(tmp_path.rglob("greet.py")), "greet.py was not created"
