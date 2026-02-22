"""Unit tests for CopilotEval."""

from __future__ import annotations

from pytest_skill_engineering.copilot.eval import CopilotEval, _parse_agent_file


class TestCopilotAgentDefaults:
    """Test default values."""

    def test_default_values(self):
        agent = CopilotEval(name="test")
        assert agent.name == "test"
        assert agent.model is None
        assert agent.max_turns == 25
        assert agent.timeout_s == 300.0
        assert agent.auto_confirm is True
        assert agent.instructions is None
        assert agent.working_directory is None

    def test_custom_values(self):
        agent = CopilotEval(
            name="custom",
            model="gpt-4.1",
            max_turns=10,
            timeout_s=60.0,
            auto_confirm=False,
            instructions="Be helpful",
            working_directory="/tmp/test",
        )
        assert agent.model == "gpt-4.1"
        assert agent.max_turns == 10
        assert agent.timeout_s == 60.0
        assert agent.auto_confirm is False

    def test_frozen(self):
        agent = CopilotEval(name="frozen")
        try:
            agent.name = "mutated"  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass  # Expected — frozen dataclass


class TestBuildSessionConfig:
    """Test build_session_config() method."""

    def test_minimal_config(self):
        agent = CopilotEval(name="minimal")
        config = agent.build_session_config()
        assert isinstance(config, dict)
        # None fields should be omitted entirely
        assert "model" not in config

    def test_full_config(self):
        agent = CopilotEval(
            name="full",
            model="claude-sonnet-4",
            reasoning_effort="high",
            instructions="Be helpful",
            max_turns=10,
            allowed_tools=["create_file"],
            excluded_tools=["run_in_terminal"],
            working_directory="/tmp/test",
        )
        config = agent.build_session_config()
        assert config["model"] == "claude-sonnet-4"
        assert config["reasoning_effort"] == "high"
        assert config["system_message"] == {"mode": "append", "content": "Be helpful"}
        assert "maxTurns" not in config  # max_turns is NOT part of SDK SessionConfig
        assert config["available_tools"] == ["create_file"]
        assert config["excluded_tools"] == ["run_in_terminal"]
        assert config["working_directory"] == "/tmp/test"

    def test_mcp_servers_included(self):
        agent = CopilotEval(
            name="mcp",
            mcp_servers={
                "my-server": {"command": "python", "args": ["-m", "my_server"]},
            },
        )
        config = agent.build_session_config()
        assert "mcp_servers" in config
        assert len(config["mcp_servers"]) == 1

    def test_system_message_replace_mode(self):
        agent = CopilotEval(
            name="replace",
            instructions="Custom system message",
            system_message_mode="replace",
        )
        config = agent.build_session_config()
        assert config["system_message"] == {
            "mode": "replace",
            "content": "Custom system message",
        }

    def test_no_system_message_without_instructions(self):
        agent = CopilotEval(name="no-instructions")
        config = agent.build_session_config()
        assert "system_message" not in config

    def test_extra_config_merged(self):
        agent = CopilotEval(
            name="extra",
            extra_config={"customField": "value"},
        )
        config = agent.build_session_config()
        assert config["customField"] == "value"

    def test_skill_directories_included(self):
        agent = CopilotEval(
            name="skilled",
            skill_directories=["/path/to/skills", "/other/skills"],
        )
        config = agent.build_session_config()
        assert config["skill_directories"] == ["/path/to/skills", "/other/skills"]

    def test_skill_directories_omitted_when_empty(self):
        agent = CopilotEval(name="no-skills")
        config = agent.build_session_config()
        assert "skill_directories" not in config

    def test_disabled_skills_included(self):
        agent = CopilotEval(
            name="restrict",
            disabled_skills=["code-search"],
        )
        config = agent.build_session_config()
        assert config["disabled_skills"] == ["code-search"]

    def test_custom_agents_included(self):
        agent = CopilotEval(
            name="multi",
            custom_agents=[
                {"name": "test-writer", "prompt": "Write tests", "tools": ["create_file"]}
            ],
        )
        config = agent.build_session_config()
        assert len(config["custom_agents"]) == 1
        assert config["custom_agents"][0]["name"] == "test-writer"

    def test_custom_agents_omitted_when_empty(self):
        agent = CopilotEval(name="no-custom")
        config = agent.build_session_config()
        assert "custom_agents" not in config


class TestParseAgentFile:
    """Unit tests for _parse_agent_file()."""

    def test_with_full_frontmatter(self, tmp_path):
        f = tmp_path / "test-specialist.agent.md"
        f.write_text(
            "---\nname: test-specialist\ndescription: Writes tests\ntools:\n  - read\n  - search\n---\nYou are a testing specialist.",
            encoding="utf-8",
        )
        result = _parse_agent_file(f)
        assert result["name"] == "test-specialist"
        assert result["description"] == "Writes tests"
        assert result["prompt"] == "You are a testing specialist."
        assert result["tools"] == ["read", "search"]

    def test_without_frontmatter(self, tmp_path):
        f = tmp_path / "my-agent.agent.md"
        f.write_text("You are a helpful agent.", encoding="utf-8")
        result = _parse_agent_file(f)
        assert result["name"] == "my-agent"
        assert result["prompt"] == "You are a helpful agent."
        assert "description" not in result
        assert "tools" not in result

    def test_name_derived_from_filename(self, tmp_path):
        f = tmp_path / "security-reviewer.agent.md"
        f.write_text("---\ndescription: Reviews security\n---\nCheck for vulns.", encoding="utf-8")
        result = _parse_agent_file(f)
        assert result["name"] == "security-reviewer"

    def test_mcp_servers_key_normalised(self, tmp_path):
        f = tmp_path / "mcp-agent.agent.md"
        f.write_text(
            "---\nname: mcp-agent\nmcp-servers:\n  my-server:\n    type: local\n    command: npx\n---\nDo things.",
            encoding="utf-8",
        )
        result = _parse_agent_file(f)
        assert "mcp_servers" in result
        assert "my-server" in result["mcp_servers"]


class TestFromCopilotConfig:
    """Tests for CopilotEval.from_copilot_config()."""

    def test_empty_dir_returns_defaults(self, tmp_path):
        agent = CopilotEval.from_copilot_config(tmp_path)
        assert agent.instructions is None
        assert agent.custom_agents == []

    def test_loads_copilot_instructions(self, tmp_path):
        github = tmp_path / ".github"
        github.mkdir()
        (github / "copilot-instructions.md").write_text("Always add type hints.", encoding="utf-8")
        agent = CopilotEval.from_copilot_config(tmp_path)
        assert agent.instructions == "Always add type hints."

    def test_loads_agents(self, tmp_path):
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "tester.agent.md").write_text(
            "---\nname: tester\ndescription: Writes tests\n---\nWrite tests.",
            encoding="utf-8",
        )
        agent = CopilotEval.from_copilot_config(tmp_path)
        assert len(agent.custom_agents) == 1
        assert agent.custom_agents[0]["name"] == "tester"
        assert agent.custom_agents[0]["prompt"] == "Write tests."

    def test_loads_from_custom_path(self, tmp_path):
        """Any arbitrary directory can be pointed at — not just 'the project'."""
        config_dir = tmp_path / "shared-team-config"
        agents_dir = config_dir / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "reviewer.agent.md").write_text(
            "---\nname: reviewer\n---\nReview code.", encoding="utf-8"
        )
        agent = CopilotEval.from_copilot_config(config_dir)
        assert len(agent.custom_agents) == 1
        assert agent.custom_agents[0]["name"] == "reviewer"

    def test_overrides_applied(self, tmp_path):
        github = tmp_path / ".github"
        github.mkdir()
        (github / "copilot-instructions.md").write_text("Base instructions.", encoding="utf-8")
        agent = CopilotEval.from_copilot_config(
            tmp_path, instructions="Override instructions.", model="claude-opus-4.5"
        )
        assert agent.instructions == "Override instructions."
        assert agent.model == "claude-opus-4.5"

    def test_multiple_agents_sorted(self, tmp_path):
        agents_dir = tmp_path / ".github" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "b-agent.agent.md").write_text(
            "---\nname: b-agent\n---\nB.", encoding="utf-8"
        )
        (agents_dir / "a-agent.agent.md").write_text(
            "---\nname: a-agent\n---\nA.", encoding="utf-8"
        )
        agent = CopilotEval.from_copilot_config(tmp_path)
        names = [a["name"] for a in agent.custom_agents]
        assert names == ["a-agent", "b-agent"]  # sorted by filename
