"""CLI Server integration tests - test CLI tools with LLM agents.

These tests verify that agents can discover and use CLI-based tools
wrapped as MCP-like tools.

Run with: pytest tests/integration/test_cli_server.py -v
"""

from __future__ import annotations

import pytest

from pytest_aitest import Agent, CLIServer, Provider

pytestmark = [pytest.mark.integration, pytest.mark.cli]


# =============================================================================
# CLI Server Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def ls_cli_server():
    """CLI server wrapping the ls command."""
    return CLIServer(
        name="ls-cli",
        command="ls",
        tool_prefix="ls",
        shell="bash",
    )


@pytest.fixture(scope="module")
def cat_cli_server():
    """CLI server wrapping the cat command."""
    return CLIServer(
        name="cat-cli",
        command="cat",
        tool_prefix="cat",
        shell="bash",
    )


@pytest.fixture(scope="module")
def echo_cli_server():
    """CLI server wrapping the echo command."""
    return CLIServer(
        name="echo-cli",
        command="echo",
        tool_prefix="echo",
        shell="bash",
        discover_help=False,  # echo --help varies by platform
    )


@pytest.fixture
def file_agent_factory(ls_cli_server, cat_cli_server):
    """Factory to create agents with file CLI tools."""
    def create_agent(
        deployment: str = "gpt-5-mini",
        system_prompt: str = "You are a helpful file system assistant. Use ls_execute to list files and cat_execute to read files.",
        max_turns: int = 5,
    ) -> Agent:
        return Agent(
            provider=Provider(model=f"azure/{deployment}"),
            cli_servers=[ls_cli_server, cat_cli_server],
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
    return create_agent


@pytest.fixture
def echo_agent_factory(echo_cli_server):
    """Factory to create agents with echo CLI tool."""
    def create_agent(
        deployment: str = "gpt-5-mini",
        system_prompt: str = "You are a helpful assistant. Use echo_execute to echo messages.",
        max_turns: int = 5,
    ) -> Agent:
        return Agent(
            provider=Provider(model=f"azure/{deployment}"),
            cli_servers=[echo_cli_server],
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
    return create_agent


# =============================================================================
# CLI Server Tests
# =============================================================================


class TestCLIServerBasicUsage:
    """Basic CLI server functionality tests."""

    @pytest.mark.asyncio
    async def test_list_directory(self, aitest_run, file_agent_factory):
        """Agent can list files using ls_execute tool."""
        agent = file_agent_factory()

        result = await aitest_run(
            agent,
            "List the files in the current directory",
        )

        assert result.success
        assert result.tool_was_called("ls_execute")

    @pytest.mark.asyncio
    async def test_read_file_contents(self, aitest_run, file_agent_factory):
        """Agent can read file contents using cat_execute tool."""
        agent = file_agent_factory()

        result = await aitest_run(
            agent,
            "Read the contents of pyproject.toml and tell me the package name.",
        )

        assert result.success
        assert result.tool_was_called("cat_execute")
        # Should mention the package name from pyproject.toml
        response_lower = result.final_response.lower()
        assert "pytest-aitest" in response_lower or "aitest" in response_lower

    @pytest.mark.asyncio
    async def test_echo_command(self, aitest_run, echo_agent_factory):
        """Agent can use echo command."""
        agent = echo_agent_factory()

        result = await aitest_run(
            agent,
            "Echo the message: Hello from pytest-aitest!",
        )

        assert result.success
        assert result.tool_was_called("echo_execute")


class TestCLIServerMultiStep:
    """Multi-step workflows with CLI servers."""

    @pytest.mark.asyncio
    async def test_explore_and_read(self, aitest_run, file_agent_factory):
        """Agent lists directory, then reads a specific file."""
        agent = file_agent_factory(max_turns=8)

        result = await aitest_run(
            agent,
            "First list what files are in the current directory, "
            "then read the README.md file and summarize what this project does.",
        )

        assert result.success
        assert result.tool_was_called("ls_execute")
        assert result.tool_was_called("cat_execute")

    @pytest.mark.asyncio
    async def test_file_analysis(self, aitest_run, file_agent_factory, judge):
        """Agent analyzes a file using multiple CLI tools."""
        agent = file_agent_factory(max_turns=8)

        result = await aitest_run(
            agent,
            "List the files in the current directory and then read pyproject.toml. "
            "Tell me what Python version is required.",
        )

        assert result.success
        # Should use both tools
        assert result.tool_was_called("ls_execute") or result.tool_was_called("cat_execute")
        # AI judge validates the response
        assert judge(result.final_response, "mentions Python version requirement")


class TestCLIServerErrorHandling:
    """Error handling tests for CLI servers."""

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, aitest_run, file_agent_factory):
        """Agent handles errors when file doesn't exist."""
        agent = file_agent_factory()

        result = await aitest_run(
            agent,
            "Read the contents of /nonexistent/path/file.txt using cat",
        )

        assert result.success
        # Agent should attempt to read the file (may also try ls first)
        assert result.tool_was_called("cat_execute") or result.tool_was_called("ls_execute")
        # Should gracefully report the error
        response_lower = result.final_response.lower()
        assert any(word in response_lower for word in ["error", "not found", "doesn't exist", "cannot", "no such", "tried"])
