"""Level 09 — CLI / shell tool usage: verify Copilot can run shell commands.

The Pydantic harness wraps shell commands via CLIServer (custom toolset).
Copilot has NATIVE terminal/shell tools built in — no CLIServer needed.
We simply instruct the agent and verify it uses shell commands to complete
file-system and pipeline tasks.

Mirrors pydantic/test_09_cli.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_09_cli.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]


class TestShellCommandBasic:
    """Basic shell command execution via Copilot's native tools."""

    async def test_create_file_with_echo(self, copilot_eval, tmp_path):
        """Agent uses shell to create a file via echo + redirection."""
        agent = CopilotEval(
            name="shell-echo",
            instructions=(
                "You can run shell commands. Use them to complete tasks. "
                "Prefer shell commands over file-creation tools when the user "
                "explicitly asks for shell usage."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Use a shell command (echo with redirection) to create a file "
            "called hello.txt containing exactly 'Hello World'.",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "hello.txt").exists(), "hello.txt was not created"

        content = (tmp_path / "hello.txt").read_text().strip()
        assert "Hello World" in content, (
            f"Expected 'Hello World' in hello.txt, got: {content!r}"
        )

    async def test_list_directory_contents(self, copilot_eval, tmp_path):
        """Agent lists directory contents and reports filenames."""
        (tmp_path / "alpha.txt").write_text("A")
        (tmp_path / "beta.txt").write_text("B")
        (tmp_path / "gamma.py").write_text("C")

        agent = CopilotEval(
            name="shell-ls",
            instructions="You can run shell commands to inspect the file system.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "List the files in the current directory and tell me their names.",
        )
        assert result.success, f"Agent failed: {result.error}"

        response = (result.final_response or "").lower()
        assert "alpha" in response and "beta" in response, (
            "Agent did not report the expected filenames.\n"
            f"Response: {result.final_response}"
        )


class TestShellMultiStep:
    """Multi-step workflows using shell commands."""

    async def test_create_and_read_back(self, copilot_eval, tmp_path):
        """Agent creates a file with shell, then reads it back to confirm."""
        agent = CopilotEval(
            name="shell-multi",
            instructions=(
                "You can run shell commands. Complete all steps in order."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Step 1: Use mkdir to create a directory called 'data'.\n"
            "Step 2: Use echo to create data/config.txt containing 'debug=true'.\n"
            "Step 3: Use cat to read data/config.txt and confirm the contents.",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "data" / "config.txt").exists(), "data/config.txt was not created"

        content = (tmp_path / "data" / "config.txt").read_text().strip()
        assert "debug=true" in content, (
            f"Expected 'debug=true' in data/config.txt, got: {content!r}"
        )

    async def test_shell_pipeline(self, copilot_eval, tmp_path):
        """Agent uses a shell pipeline (echo | wc, grep, etc.) to process text."""
        (tmp_path / "names.txt").write_text("Alice\nBob\nCharlie\nDiana\nEdward\n")

        agent = CopilotEval(
            name="shell-pipeline",
            instructions="You can run shell commands including pipelines.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Count the number of lines in names.txt using shell commands "
            "and tell me the result.",
        )
        assert result.success, f"Agent failed: {result.error}"

        response = result.final_response or ""
        assert "5" in response, (
            f"Expected the agent to report 5 lines. Response: {response}"
        )


class TestShellErrorHandling:
    """Agent handles shell errors gracefully."""

    async def test_nonexistent_file_error(self, copilot_eval, tmp_path):
        """Agent handles 'file not found' gracefully when reading a missing file."""
        agent = CopilotEval(
            name="shell-error",
            instructions="You can run shell commands. Report errors clearly.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Use cat to read a file called nonexistent.txt in the current directory "
            "and tell me what happened.",
        )
        assert result.success, f"Agent failed: {result.error}"

        response = (result.final_response or "").lower()
        assert any(
            phrase in response
            for phrase in [
                "not found",
                "no such file",
                "does not exist",
                "doesn't exist",
                "error",
                "cannot",
                "failed",
            ]
        ), (
            "Agent did not report the error from reading a nonexistent file.\n"
            f"Response: {result.final_response}"
        )
