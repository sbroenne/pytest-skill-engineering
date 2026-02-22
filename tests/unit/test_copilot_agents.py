"""Unit tests for custom agent file loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_aitest.copilot.agents import (
    _extract_frontmatter,
    _name_from_path,
    load_custom_agent,
    load_custom_agents,
)

# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


class TestExtractFrontmatter:
    """Test YAML frontmatter extraction and parsing."""

    def test_with_frontmatter(self):
        content = "---\ndescription: 'Test agent'\nmaturity: stable\n---\n\n# Body"
        metadata, body = _extract_frontmatter(content)
        assert metadata["description"] == "Test agent"
        assert metadata["maturity"] == "stable"
        assert body.strip() == "# Body"

    def test_without_frontmatter(self):
        content = "# No frontmatter here\n\nJust markdown."
        metadata, body = _extract_frontmatter(content)
        assert metadata == {}
        assert body == content

    def test_complex_frontmatter(self):
        content = (
            "---\n"
            "description: 'Complex agent'\n"
            "handoffs:\n"
            "  - label: 'Plan'\n"
            "    agent: task-planner\n"
            "    prompt: /task-plan\n"
            "    send: true\n"
            "  - label: 'Review'\n"
            "    agent: task-reviewer\n"
            "    prompt: /task-review\n"
            "    send: true\n"
            "---\n\n"
            "# Agent body"
        )
        metadata, body = _extract_frontmatter(content)
        assert metadata["description"] == "Complex agent"
        assert len(metadata["handoffs"]) == 2
        assert metadata["handoffs"][0]["agent"] == "task-planner"
        assert metadata["handoffs"][1]["label"] == "Review"

    def test_invalid_yaml(self):
        content = "---\n: invalid: yaml: [unbalanced\n---\n\n# Body"
        metadata, body = _extract_frontmatter(content)
        assert metadata == {}
        assert body.strip() == "# Body"

    def test_non_dict_yaml(self):
        content = "---\n- just a list\n- not a dict\n---\n\n# Body"
        metadata, body = _extract_frontmatter(content)
        assert metadata == {}


# ---------------------------------------------------------------------------
# Name derivation
# ---------------------------------------------------------------------------


class TestNameFromPath:
    """Test agent name derivation from file paths."""

    def test_agent_md_suffix(self):
        assert _name_from_path(Path("task-researcher.agent.md")) == "task-researcher"

    def test_nested_path(self):
        assert _name_from_path(Path("agents/rpi-agent.agent.md")) == "rpi-agent"

    def test_plain_md(self):
        assert _name_from_path(Path("something.md")) == "something"


# ---------------------------------------------------------------------------
# Single agent loading
# ---------------------------------------------------------------------------


class TestLoadCustomAgent:
    """Test loading individual .agent.md files."""

    def test_load_agent(self, tmp_path):
        agent_file = tmp_path / "test-agent.agent.md"
        agent_file.write_text(
            "---\ndescription: 'A test agent'\nmaturity: stable\n---\n\n"
            "# Test Agent\n\nDoes test things.",
            encoding="utf-8",
        )
        result = load_custom_agent(agent_file)
        assert result["name"] == "test-agent"
        assert result["prompt"] == "# Test Agent\n\nDoes test things."
        assert result["description"] == "A test agent"
        assert result["metadata"]["maturity"] == "stable"

    def test_missing_description(self, tmp_path):
        agent_file = tmp_path / "no-desc.agent.md"
        agent_file.write_text(
            "---\nmaturity: experimental\n---\n\n# Agent\n\nBody.",
            encoding="utf-8",
        )
        result = load_custom_agent(agent_file)
        assert result["description"] == ""
        assert result["metadata"]["maturity"] == "experimental"

    def test_no_frontmatter(self, tmp_path):
        agent_file = tmp_path / "bare.agent.md"
        agent_file.write_text("# Bare Agent\n\nNo frontmatter.", encoding="utf-8")
        result = load_custom_agent(agent_file)
        assert result["name"] == "bare"
        assert result["description"] == ""
        assert result["metadata"] == {}

    def test_overrides(self, tmp_path):
        agent_file = tmp_path / "overridable.agent.md"
        agent_file.write_text(
            "---\ndescription: 'Original'\n---\n\n# Agent",
            encoding="utf-8",
        )
        result = load_custom_agent(
            agent_file,
            overrides={"tools": ["read_file"], "description": "Overridden"},
        )
        assert result["tools"] == ["read_file"]
        assert result["description"] == "Overridden"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Agent file not found"):
            load_custom_agent(Path("/nonexistent/agent.agent.md"))

    def test_empty_body(self, tmp_path):
        agent_file = tmp_path / "empty.agent.md"
        agent_file.write_text("---\ndescription: 'Empty'\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="no content after frontmatter"):
            load_custom_agent(agent_file)


# ---------------------------------------------------------------------------
# Directory loading
# ---------------------------------------------------------------------------


class TestLoadCustomAgents:
    """Test loading all agents from a directory."""

    @pytest.fixture
    def agents_dir(self, tmp_path):
        """Create a directory with agent files."""
        d = tmp_path / "agents"
        d.mkdir()
        (d / "alpha.agent.md").write_text(
            "---\ndescription: 'Alpha'\n---\n\n# Alpha", encoding="utf-8"
        )
        (d / "beta.agent.md").write_text(
            "---\ndescription: 'Beta'\n---\n\n# Beta", encoding="utf-8"
        )
        (d / "gamma.agent.md").write_text(
            "---\ndescription: 'Gamma'\n---\n\n# Gamma", encoding="utf-8"
        )
        # Non-agent file in the directory
        (d / "README.md").write_text("Not an agent.", encoding="utf-8")
        return d

    def test_loads_all(self, agents_dir):
        agents = load_custom_agents(agents_dir)
        names = [a["name"] for a in agents]
        assert names == ["alpha", "beta", "gamma"]

    def test_include_filter(self, agents_dir):
        agents = load_custom_agents(agents_dir, include={"alpha", "gamma"})
        names = [a["name"] for a in agents]
        assert names == ["alpha", "gamma"]

    def test_exclude_filter(self, agents_dir):
        agents = load_custom_agents(agents_dir, exclude={"beta"})
        names = [a["name"] for a in agents]
        assert names == ["alpha", "gamma"]

    def test_per_agent_overrides(self, agents_dir):
        agents = load_custom_agents(
            agents_dir,
            overrides={"beta": {"tools": ["create_file"]}},
        )
        beta = next(a for a in agents if a["name"] == "beta")
        assert beta["tools"] == ["create_file"]
        alpha = next(a for a in agents if a["name"] == "alpha")
        assert "tools" not in alpha

    def test_directory_not_found(self):
        with pytest.raises(FileNotFoundError, match="Agent directory not found"):
            load_custom_agents(Path("/nonexistent/agents"))

    def test_ignores_non_agent_files(self, agents_dir):
        agents = load_custom_agents(agents_dir)
        names = [a["name"] for a in agents]
        assert "README" not in names

    def test_sorted_by_name(self, agents_dir):
        agents = load_custom_agents(agents_dir)
        names = [a["name"] for a in agents]
        assert names == sorted(names)
