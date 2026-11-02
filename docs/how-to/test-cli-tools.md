---
description: "Run any CLI directly through a shared SDK tool and verify its output independently."
---

# How to test CLI tools

Run the selected executable directly with an argument array. Use
`create_command_tool` for any CLI: the command under test, its native help,
setup, discovery, and supporting commands. No PowerShell, cmd, Bash, or MCP
wrapper is required. Arguments are not shell text: spaces, quotes, empty
arguments, paths, and shell operators are passed literally.

## Preferred pattern: direct process tool

This example requires Git on `PATH`. The fixture creates a disposable repository
with a direct process call. Copilot gets only a direct Git tool; the test checks
the actual index and file rather than trusting its final reply.

```python
from __future__ import annotations

import shutil
import subprocess

from pytest_skill_engineering.copilot import CopilotEval, create_command_tool


async def test_git_add(copilot_eval, tmp_path):
    git = shutil.which("git")
    assert git is not None, "Install Git before running this test"
    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "note.txt").write_text("hello\n", encoding="utf-8")
    tool = create_command_tool(git, name="git", cwd=tmp_path, timeout_s=30)
    agent = CopilotEval(
        name="git-stage-file",
        model="gpt-5.6-sol",
        client_mode="empty",
        instructions=(
            "Use the git tool directly for all Git commands, including help "
            "and discovery. Supply each argument separately, without shell "
            "quoting. Use Git's native help when needed."
        ),
        working_directory=str(tmp_path),
        allowed_tools=["git"],
        extra_config={"tools": [tool]},
        timeout_s=120,
    )
    result = await copilot_eval(
        agent, "Stage note.txt with git add. Do not edit the file or create a commit."
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
```

Attach additional executables as separate named tools in `extra_config["tools"]`
and `allowed_tools` when the task needs them. Use the same direct-process rule
for supporting tools; do not silently reintroduce a shell for setup or discovery.
Keep each product's native command names and help, rather than inventing a
framework-specific command language.

## Input, output, and process ownership

`create_command_tool(executable, *, name="run_command", cwd=None, env=None,
timeout_s=30.0, cleanup_timeout_s=5.0, terminate_descendants=True)` returns a
Copilot SDK `Tool`.

- The caller selects the executable, directory, environment, and time limits.
  The model supplies `{"args": ["--help"]}` and optional `"stdin": "text"`.
  Standard input is UTF-8; absent input is closed, not an interactive terminal.
- `cwd` defaults to the caller's directory when the tool is created. `env`
  overrides the environment inherited at each invocation; the tool copies the
  supplied overrides at creation. Per-case environment values set later remain
  inherited unless explicitly overridden.
  Use an absolute executable path when selection must not depend on `PATH`.
- The JSON result has `stdout`, `stderr`, `exit_code`, `error`, and `error_kind`.
  Text is decoded as UTF-8 with replacement for invalid bytes; `stdout_base64`
  and `stderr_base64` preserve the exact bytes, including native line endings.
  Output is not truncated.
- Invalid input, startup errors, nonzero exits, timeouts, and cleanup errors
  return `ToolResult(result_type="failure")`, not success-shaped output.
  `error_kind` is respectively `invalid_input`, `start`, `exit`, `timeout`,
  or `cleanup`; it is null on success. A command that never starts has a null
  exit code.
- Timeout and cancellation stop the owned process and descendants using a
  process group on POSIX or a kill-on-close job on Windows, then allow up to
  `cleanup_timeout_s` for output draining. Partial output is retained.
  Cancellation still propagates as `CommandCancelledError` (an
  `asyncio.CancelledError`), with the partial `ToolResult` in its `result`
  attribute and `error_kind="cancelled"` unless cleanup also failed.
  Processes must not deliberately escape their group or job.

Set the caller-selected `terminate_descendants=False` only when the consumer
owns a service started by the command and must preserve its state before
cleaning it up separately. The helper then stops only the root command process,
on both timeout and cancellation. The service must not keep the command's
standard streams open; it must own its input/output and lifecycle. Otherwise
output draining can hit the cleanup limit and reports a cleanup failure.
This option is never model input.

There are no automatic retries or persistent launcher. The helper never keeps
the root command running after its tool call returns.

## Permissions and independent checks

This helper is not a security sandbox. The selected CLI can access the host
filesystem and network, and some CLIs can themselves execute arbitrary code.
Consumers own application-specific permissions and guarded adapters. Do not
give the model environment secrets or credentials through command arguments
or standard input; command input and output can appear in saved evidence.

Use an approved execution environment and independently check the application
state. Neither a successful tool call nor session completion proves the task.
An MCP server is appropriate when testing an MCP interface, not a requirement
for running a CLI directly.

## Tests specifically about shell features

Use native shell tools only when the interface under test really is a shell,
such as pipelines, redirection, shell expansion, or shell scripts. Keep those
cases explicitly separate from ordinary CLI tests. Windows batch files
(`.bat` and `.cmd`) require a shell and are rejected by the direct helper.
Choose a native executable instead. Do not use a shell merely to quote JSON,
paths, formulas, or ordinary command arguments.
