"""Level 09: direct CLI workflows; separate tests of actual shell features.

Run only when real model calls are authorized.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from pytest_copilot.copilot import CopilotTask, create_command_tool

pytestmark = [pytest.mark.copilot]


class TestDirectCommands:
    """Ordinary CLI work uses executable tools, including setup and help."""

    async def test_git_setup_and_stage(self, copilot_run, tmp_path):
        git = shutil.which("git")
        assert git is not None, "Install Git before running this test"
        (tmp_path / "note.txt").write_text("hello\n", encoding="utf-8")
        agent = CopilotTask(
            name="direct-git",
            client_mode="empty",
            instructions=(
                "Use the git tool for all commands, including setup and discovery. "
                "Supply separate arguments without shell quoting. Consult native "
                "Git help if needed. Do not edit files or create a commit."
            ),
            working_directory=str(tmp_path),
            allowed_tools=["git"],
            extra_config={
                "tools": [create_command_tool(git, name="git", cwd=tmp_path)],
            },
        )
        result = await copilot_run(
            agent, "Initialize this directory as a Git repository and stage note.txt."
        )
        assert result.success, result.error
        staged = subprocess.run(
            [git, "diff", "--cached", "--name-only"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        assert staged.stdout.splitlines() == ["note.txt"]
        content = subprocess.run(
            [git, "show", ":note.txt"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        assert content.stdout == "hello\n"
        assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "hello\n"
        head = subprocess.run(
            [git, "rev-parse", "--verify", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert head.returncode != 0, "The task must not create a commit"

    async def test_python_preserves_literal_arguments(self, copilot_run, tmp_path):
        script = tmp_path / "save_args.py"
        script.write_text(
            "import json, pathlib, sys\n"
            "pathlib.Path('args.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n",
            encoding="utf-8",
        )
        agent = CopilotTask(
            name="direct-python",
            client_mode="empty",
            instructions="Use the python tool with separate arguments. Do not use shell quoting.",
            working_directory=str(tmp_path),
            allowed_tools=["python"],
            extra_config={
                "tools": [create_command_tool(sys.executable, name="python", cwd=tmp_path)],
            },
        )
        result = await copilot_run(
            agent,
            "Run save_args.py with these three literal arguments, in order: "
            'an empty string; a "quoted" value; $HOME | >.',
        )
        assert result.success, result.error
        assert json.loads((tmp_path / "args.json").read_text(encoding="utf-8")) == [
            "",
            'a "quoted" value',
            "$HOME | >",
        ]


class TestShellFeatures:
    """Only these cases deliberately test the native shell interface."""

    async def test_create_file_with_redirection(self, copilot_run, tmp_path):
        agent = CopilotTask(
            name="shell-redirection",
            instructions="This test is about shell redirection. Use the native shell.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Use echo with shell redirection to create hello.txt containing exactly Hello World.",
        )
        assert result.success, result.error
        assert (tmp_path / "hello.txt").read_text(encoding="utf-8-sig").strip() == "Hello World"

    async def test_shell_pipeline(self, copilot_run, tmp_path):
        (tmp_path / "names.txt").write_text(
            "Alice\nBob\nCharlie\nDiana\nEdward\n", encoding="utf-8"
        )
        agent = CopilotTask(
            name="shell-pipeline",
            instructions="This test is about shell pipelines. Use the native shell.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Use a shell pipeline to count lines in names.txt. "
            "Write only the numeric count to count.txt, leaving names.txt unchanged.",
        )
        assert result.success, result.error
        assert (tmp_path / "count.txt").read_text(encoding="utf-8-sig").strip() == "5"
        assert (tmp_path / "names.txt").read_text(encoding="utf-8") == (
            "Alice\nBob\nCharlie\nDiana\nEdward\n"
        )
