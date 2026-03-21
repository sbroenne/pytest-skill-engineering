"""Level 13 — Plugin loading and testing.

Tests that plugins (directories with plugin.json, agents, skills, hooks)
can be loaded and used to create Evals that test the plugin's AI interface.

Permutation: Plugin directory structure → Eval.

Run with: pytest tests/integration/pydantic/test_13_plugins.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, Provider, load_plugin
from pytest_skill_engineering.core.plugin import PluginMetadata

from ..conftest import (
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration]

PLUGIN_DIR = Path(__file__).parents[1] / "plugins" / "banking-plugin"
CLAUDE_DIR = Path(__file__).parents[1] / "plugins" / "claude-project"


# =============================================================================
# Plugin Loading and Parsing
# =============================================================================


class TestPluginLoading:
    """Test plugin manifest parsing and component discovery."""

    def test_load_plugin_metadata(self):
        """Plugin metadata is correctly parsed from plugin.json."""
        plugin = load_plugin(PLUGIN_DIR)
        assert plugin.metadata.name == "banking-plugin"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.metadata.description

    def test_load_plugin_agents(self):
        """Custom agents are discovered from agents/ directory."""
        plugin = load_plugin(PLUGIN_DIR)
        assert len(plugin.agents) >= 1
        agent_names = [a.get("name", "") for a in plugin.agents]
        assert "banking-advisor" in agent_names

    def test_load_plugin_skills(self):
        """Skills are discovered from skills/ directory."""
        plugin = load_plugin(PLUGIN_DIR)
        assert len(plugin.skills) >= 1

    def test_load_plugin_instructions(self):
        """Instructions are loaded from instruction files."""
        plugin = load_plugin(PLUGIN_DIR)
        assert "banking assistant" in plugin.instructions.lower()

    def test_load_claude_project(self):
        """Claude Code project structure is correctly loaded."""
        plugin = load_plugin(CLAUDE_DIR)
        assert "coding assistant" in plugin.instructions.lower()
        assert len(plugin.agents) >= 1


# =============================================================================
# Eval.from_plugin — Plugin-Based Eval Creation
# =============================================================================


class TestPluginEval:
    """Test creating Evals from plugins."""

    async def test_eval_from_plugin(self, eval_run, banking_server):
        """Eval.from_plugin() creates a working eval."""
        agent = Eval.from_plugin(
            PLUGIN_DIR,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            max_turns=DEFAULT_MAX_TURNS,
            mcp_servers=[banking_server],
        )
        result = await eval_run(agent, "What is the balance of my checking account?")
        assert result.success
        assert result.tool_was_called("get_balance")

    async def test_eval_from_plugin_uses_instructions(self, eval_run, banking_server, llm_assert):
        """Eval.from_plugin() picks up copilot-instructions.md as system prompt."""
        agent = Eval.from_plugin(
            PLUGIN_DIR,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            max_turns=DEFAULT_MAX_TURNS,
            mcp_servers=[banking_server],
        )
        result = await eval_run(agent, "What are all my account balances?")
        assert result.success
        # Instructions say "include cents" — verify the agent formats amounts precisely
        assert llm_assert(
            result.final_response,
            "Includes monetary amounts with cents (e.g., $1,500.00 not just $1500).",
        )

    async def test_eval_from_claude_project(self, eval_run, banking_server):
        """Eval.from_plugin() handles Claude Code project layout (CLAUDE.md)."""
        agent = Eval.from_plugin(
            CLAUDE_DIR,
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            max_turns=DEFAULT_MAX_TURNS,
            mcp_servers=[banking_server],
        )
        result = await eval_run(agent, "What is my checking account balance?")
        assert result.success


# =============================================================================
# Plugin Metadata Integrity
# =============================================================================


class TestPluginMetadata:
    """Plugin metadata fields are correctly exposed."""

    def test_metadata_fields(self):
        """PluginMetadata has all expected fields from plugin.json."""
        plugin = load_plugin(PLUGIN_DIR)
        meta = plugin.metadata
        assert isinstance(meta, PluginMetadata)
        assert meta.name == "banking-plugin"
        assert meta.version == "1.0.0"
        assert meta.author == "pytest-skill-engineering"

    def test_claude_project_has_no_plugin_json(self):
        """Claude project without plugin.json gets default metadata."""
        plugin = load_plugin(CLAUDE_DIR)
        # No plugin.json → name derived from directory
        assert plugin.metadata.name
