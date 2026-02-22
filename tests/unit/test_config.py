"""Tests for pytest-skill-engineering config models."""

from __future__ import annotations

import os
from unittest.mock import patch

from pytest_skill_engineering.core.eval import (
    CLIServer,
    Eval,
    MCPServer,
    Provider,
    Wait,
    WaitStrategy,
)


class TestWait:
    """Tests for Wait configuration."""

    def test_ready(self) -> None:
        wait = Wait.ready()
        assert wait.strategy == WaitStrategy.READY
        assert wait.timeout_ms == 30000

    def test_ready_custom_timeout(self) -> None:
        wait = Wait.ready(timeout_ms=60000)
        assert wait.timeout_ms == 60000

    def test_for_log(self) -> None:
        wait = Wait.for_log("Server started")
        assert wait.strategy == WaitStrategy.LOG
        assert wait.pattern == "Server started"

    def test_for_tools(self) -> None:
        wait = Wait.for_tools(["read_file", "write_file"])
        assert wait.strategy == WaitStrategy.TOOLS
        assert wait.tools == ("read_file", "write_file")


class TestProvider:
    """Tests for Provider configuration."""

    def test_basic(self) -> None:
        provider = Provider(model="openai/gpt-4o-mini")
        assert provider.model == "openai/gpt-4o-mini"
        assert provider.temperature is None  # Default: let LiteLLM decide

    def test_with_temperature(self) -> None:
        provider = Provider(model="openai/gpt-4o", temperature=0.7)
        assert provider.temperature == 0.7

    def test_with_rate_limits(self) -> None:
        provider = Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000)
        assert provider.rpm == 10
        assert provider.tpm == 10000


class TestMCPServer:
    """Tests for MCPServer configuration."""

    def test_basic(self) -> None:
        server = MCPServer(command=["npx", "server"])
        assert server.command == ["npx", "server"]
        assert server.args == []
        assert server.env == {}

    def test_with_args(self) -> None:
        server = MCPServer(
            command=["python", "server.py"],
            args=["--debug", "--port", "8080"],
        )
        assert server.args == ["--debug", "--port", "8080"]

    def test_env_expansion(self) -> None:
        with patch.dict(os.environ, {"SECRET": "value123"}):
            server = MCPServer(
                command=["cmd"],
                env={"API_KEY": "${SECRET}"},
            )
            assert server.env["API_KEY"] == "value123"


class TestCLIServer:
    """Tests for CLIServer configuration."""

    def test_basic(self) -> None:
        server = CLIServer(name="git", command="git", tool_prefix="git")
        assert server.name == "git"
        assert server.command == "git"
        assert server.tool_prefix == "git"

    def test_defaults(self) -> None:
        server = CLIServer(name="cli", command="cli", tool_prefix="cli")
        assert server.shell is None  # Auto-detect
        assert server.cwd is None
        assert server.env == {}
        assert server.discover_help is False  # LLM must discover help itself

    def test_with_cwd(self) -> None:
        server = CLIServer(
            name="run",
            command="./run.sh",
            tool_prefix="run",
            cwd="/tmp/workspace",
        )
        assert server.cwd == "/tmp/workspace"

    def test_with_shell(self) -> None:
        server = CLIServer(
            name="pwsh",
            command="dir",
            tool_prefix="dir",
            shell="powershell",
        )
        assert server.shell == "powershell"

    def test_discover_help_disabled(self) -> None:
        server = CLIServer(
            name="fast",
            command="fast",
            tool_prefix="fast",
            discover_help=False,
        )
        assert server.discover_help is False

    def test_env_expansion(self) -> None:
        with patch.dict(os.environ, {"SECRET": "value123"}):
            server = CLIServer(
                name="cli",
                command="cli",
                tool_prefix="cli",
                env={"API_KEY": "${SECRET}"},
            )
            assert server.env["API_KEY"] == "value123"


class TestAgent:
    """Tests for Eval configuration."""

    def test_minimal(self) -> None:
        agent = Eval(provider=Provider(model="openai/gpt-4o"))
        assert agent.provider.model == "openai/gpt-4o"
        assert agent.mcp_servers == []
        assert agent.cli_servers == []
        assert agent.max_turns == 10

    def test_with_servers(self) -> None:
        mcp = MCPServer(command=["mcp-server"])
        cli = CLIServer(name="cli", command="cli-tool", tool_prefix="cli")

        agent = Eval(
            provider=Provider(model="openai/gpt-4o"),
            mcp_servers=[mcp],
            cli_servers=[cli],
            system_prompt="Be helpful.",
            max_turns=5,
        )

        assert len(agent.mcp_servers) == 1
        assert len(agent.cli_servers) == 1
        assert agent.system_prompt == "Be helpful."
        assert agent.max_turns == 5
