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

## When you need restricted command access

The framework does not provide a command wrapper. If your test needs restricted
command access rather than general shell access, expose approved commands through
your own MCP server. Your server owns command validation and permissions; your
test independently verifies the resulting state.

Attach your server configuration to Copilot:

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
