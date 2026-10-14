---
description: "Run a CLI task through Copilot and verify the resulting repository state independently."
---

# How to test CLI tools

Use Copilot's native shell tools for an ordinary CLI workflow. Initialize a
disposable workspace, ask for a concrete change, then check the resulting state
with your own process—not the assistant's final reply.

## Preferred pattern: native shell workflow

This test requires Git on `PATH`. It creates a repository and verifies that
Copilot stages the seeded file without changing its contents:

```python
from __future__ import annotations

import subprocess

from pytest_skill_engineering.copilot import CopilotEval


async def test_git_add(copilot_eval, tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "note.txt").write_text("hello\n", encoding="utf-8")
    agent = CopilotEval(
        name="git-stage-file",
        model="gpt-5.6-sol",
        instructions="Use terminal tools for the requested Git operation.",
        working_directory=str(tmp_path),
        timeout_s=120,
    )
    result = await copilot_eval(
        agent, "Stage note.txt with git add. Do not edit the file or create a commit."
    )

    assert result.success, result.error
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert staged.stdout.splitlines() == ["note.txt"]
    content = subprocess.run(
        ["git", "show", ":note.txt"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert content.stdout == "hello\n"
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "hello\n"
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert head.returncode != 0, "The task must not create a commit"
```

This verifies the staged artifact, unchanged working file, and absence of a commit.
Keep the test in an approved environment: `working_directory` is not a sandbox,
and permissions are auto-approved by default.

## When you have a wrapped CLI tool

`CLIServer` is a lower-level configuration helper for exposing a CLI as a
single tool. It is not an argument to `CopilotEval`, and its constructor does
not accept `name`.

```python
from pytest_skill_engineering import CLIServer

git_server = CLIServer(
    command="git",
    tool_prefix="git",
    shell="none",
    discover_help=True,
)
```

Use a wrapper when you need a constrained command surface rather than general
shell access. Your adapter owns command validation, permissions, and state
verification.

## Configuration options

```python
git_server = CLIServer(
    command="git",
    tool_prefix="git",
    shell="none",
    cwd="path/to/test-repo",
    env={"LC_ALL": "C"},
    discover_help=False,
    help_flag="--help",
    timeout=30,
    description="Run approved Git commands.",
)
```

With `shell="none"`, the command and tool arguments are split into direct process
arguments without shell expansion. Windows backslashes are preserved; quote
paths containing spaces. Grouping quotes are removed, while quoted empty
arguments stay empty arguments. The default `shell=None` auto-selects a shell;
it is not the same as `"none"`.

## Complete Copilot-facing example

For a CLI exposed by your own MCP server, attach the server configuration:

```python
import sys

GIT_MCP = {
    "git": {
        "command": sys.executable,
        "args": ["-m", "my_project.git_mcp"],
        "tools": ["*"],
    }
}
```

This is an illustrative configuration requiring your `my_project.git_mcp`
module. Pass it as `CopilotEval(mcp_servers=GIT_MCP, ...)`, seed the server's
test repository, and perform the same independent index checks. Merely
attaching the wrapper or observing a tool call does not verify the Git task.

See [Test MCP servers](test-mcp-servers.md) for transports and tool restrictions.
