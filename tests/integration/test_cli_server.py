"""CLI Server integration tests - test CLI tools with LLM agents.

These tests verify that agents can discover and use CLI-based tools
wrapped as MCP-like tools.

Run with: pytest tests/integration/test_cli_server.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import CLIServer, Eval, Provider

from .conftest import (
    DEFAULT_MAX_TURNS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
)

pytestmark = [pytest.mark.integration, pytest.mark.cli]

# System prompt for file CLI tools
FILE_CLI_PROMPT = (
    "You are a helpful file system assistant. "
    "Use ls_execute to list files and cat_execute to read files."
)
ECHO_CLI_PROMPT = "You are a helpful assistant. Use echo_execute to echo messages."


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


# =============================================================================
# CLI Server Tests
# =============================================================================


class TestCLIServerBasicUsage:
    """Basic CLI server functionality tests."""

    @pytest.mark.asyncio
    async def test_list_directory(self, eval_run, ls_cli_server, cat_cli_server):
        """Eval can list files using ls_execute tool."""
        agent = Eval(
            name="ls-test",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            cli_servers=[ls_cli_server, cat_cli_server],
            system_prompt=FILE_CLI_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(
            agent,
            "List the files in the current directory",
        )

        assert result.success
        assert result.tool_was_called("ls_execute")

    @pytest.mark.asyncio
    async def test_read_file_contents(self, eval_run, ls_cli_server, cat_cli_server):
        """Eval can read file contents using cat_execute tool."""
        agent = Eval(
            name="cat-test",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            cli_servers=[ls_cli_server, cat_cli_server],
            system_prompt=FILE_CLI_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(
            agent,
            "Read the contents of pyproject.toml and tell me the package name.",
        )

        assert result.success
        assert result.tool_was_called("cat_execute")
        # Should mention the package name from pyproject.toml
        response_lower = result.final_response.lower()
        assert "pytest-skill-engineering" in response_lower or "aitest" in response_lower

    @pytest.mark.asyncio
    async def test_echo_command(self, eval_run, echo_cli_server):
        """Eval can use echo command."""
        agent = Eval(
            name="echo-test",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            cli_servers=[echo_cli_server],
            system_prompt=ECHO_CLI_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(
            agent,
            "Echo the message: Hello from pytest-skill-engineering!",
        )

        assert result.success
        assert result.tool_was_called("echo_execute")


class TestCLIServerMultiStep:
    """Multi-step workflows with CLI servers."""

    @pytest.mark.asyncio
    async def test_explore_and_read(self, eval_run, ls_cli_server, cat_cli_server):
        """Eval lists directory, then reads a specific file."""
        agent = Eval(
            name="explore-read",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            cli_servers=[ls_cli_server, cat_cli_server],
            system_prompt=FILE_CLI_PROMPT,
            max_turns=8,
        )

        result = await eval_run(
            agent,
            "First list what files are in the current directory, "
            "then read the README.md file and summarize what this project does.",
        )

        assert result.success
        assert result.tool_was_called("ls_execute")
        assert result.tool_was_called("cat_execute")

    @pytest.mark.asyncio
    async def test_file_analysis(self, eval_run, ls_cli_server, cat_cli_server, llm_assert):
        """Eval analyzes a file using multiple CLI tools."""
        agent = Eval(
            name="file-analysis",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            cli_servers=[ls_cli_server, cat_cli_server],
            system_prompt=FILE_CLI_PROMPT,
            max_turns=8,
        )

        result = await eval_run(
            agent,
            "List the files in the current directory and then read pyproject.toml. "
            "Tell me what Python version is required.",
        )

        assert result.success
        # Should use both tools
        assert result.tool_was_called("ls_execute") or result.tool_was_called("cat_execute")
        # AI judge validates the response
        assert llm_assert(result.final_response, "mentions Python version requirement")


class TestCLIServerErrorHandling:
    """Error handling tests for CLI servers."""

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, eval_run, ls_cli_server, cat_cli_server):
        """Eval handles errors when file doesn't exist."""
        agent = Eval(
            name="error-handling",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            cli_servers=[ls_cli_server, cat_cli_server],
            system_prompt=FILE_CLI_PROMPT,
            max_turns=DEFAULT_MAX_TURNS,
        )

        result = await eval_run(
            agent,
            "Read the contents of /nonexistent/path/file.txt using cat",
        )

        assert result.success
        # Eval should attempt to read the file (may also try ls first)
        assert result.tool_was_called("cat_execute") or result.tool_was_called("ls_execute")
        # Should gracefully report the error
        response_lower = result.final_response.lower()
        assert any(
            word in response_lower
            for word in ["error", "not found", "doesn't exist", "cannot", "no such", "tried"]
        )
