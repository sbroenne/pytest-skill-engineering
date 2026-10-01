"""Level 13 — Plugin testing via CopilotEval.

Tests plugin loading, from_claude_config(), and SDK passthroughs
for the Copilot SDK harness.

Copilot-exclusive — CopilotEval.from_plugin() maps plugin components
to SDK session config fields (custom_agents, instructions, skill_directories).

Run with: uv run python -m pytest tests/integration/copilot/test_13_plugins.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from copilot.tools import Tool, ToolInvocation, ToolResult

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
        balances = {"checking": "$125.00", "savings": "$250.00"}
        receipt = tmp_path / "balances.txt"

        async def get_balance(invocation: ToolInvocation) -> ToolResult:
            account = (invocation.arguments or {}).get("account_type")
            if not isinstance(account, str) or account not in balances:
                return ToolResult(
                    text_result_for_llm="Error: account_type must be checking or savings.",
                    result_type="failure",
                )
            entry = f"{account}: {balances[account]}"
            with receipt.open("a", encoding="utf-8") as output:
                output.write(entry + "\n")
            return ToolResult(text_result_for_llm=entry)

        agent = CopilotEval.from_plugin(
            PLUGIN_DIR,
            model=DEFAULT_MODEL,
            working_directory=str(tmp_path),
            excluded_tools=["task"],
            extra_config={
                "tools": [
                    Tool(
                        name="get_balance",
                        description="Look up an account balance and save it to balances.txt.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "account_type": {
                                    "type": "string",
                                    "enum": ["checking", "savings"],
                                }
                            },
                            "required": ["account_type"],
                        },
                        handler=get_balance,
                    )
                ]
            },
        )
        result = await copilot_eval(
            agent,
            "Have banking-advisor use get_balance for both checking and savings accounts. "
            "The banking tool saves each balance to balances.txt.",
        )
        assert result.success, f"Failed: {result.error}"
        assert set(receipt.read_text(encoding="utf-8").splitlines()) == {
            "checking: $125.00",
            "savings: $250.00",
        }
        children = [
            invocation.result
            for invocation in result.subagent_invocations
            if invocation.name == "banking-advisor" and invocation.result is not None
        ]
        assert children, "The plugin's banking agent was not dispatched"
        assert all(
            child.configuration is not None
            and child.configuration["allowed_tools"] == ["get_balance", "transfer"]
            for child in children
        )

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
