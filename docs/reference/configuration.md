---
description: "Configure CopilotEval, MCP servers, execution controls, and JSON evidence."
---

# Configuration

`CopilotEval` configures a session; the task is passed separately to
`copilot_eval`. This page covers the common settings. The
[API reference](api.md) contains the full signature.

## Authentication

Supported authentication paths:

- `gh auth login --hostname github.com`
- `GITHUB_TOKEN` or `GH_TOKEN` in CI or automation

Eval sessions select `GITHUB_TOKEN` first, then `GH_TOKEN`. If neither
is set, the SDK uses its signed-in user. Tokens must authorize the intended
GitHub account and Copilot access.

The framework uses GitHub Copilot. There is no separate provider configuration.

## CopilotEval

```python
from pytest_skill_engineering.copilot import CopilotEval


agent = CopilotEval(
    name="my-task",
    model="gpt-5.6-sol",
    instructions="Use the supplied tools to complete the user's task.",
    timeout_s=120,
    max_tool_calls=10,
)
```

### Common settings

| Field | Meaning |
|---|---|
| `name` | Label identifying the configuration in saved evidence |
| `model` | Copilot model name; `None` uses Copilot's default |
| `instructions` | System prompt content; distinct from the user task |
| `system_message_mode` | `append` by default; `replace` replaces the SDK system message content |
| `working_directory` | Session workspace; not a security sandbox |
| `mcp_servers` | Copilot SDK server config mapping |
| `allowed_tools` | Optional global tool allow-list |
| `excluded_tools` | Tool block-list |
| `custom_agents` | Loaded `.agent.md` definitions |
| `active_agent` | Custom agent to activate at session start |
| `skill_directories` | Explicit individual skill directories or parents; enable loading and check SDK availability before sending |
| `disabled_skills` | Skill names deliberately disabled, retained in discovery evidence |
| `max_turns` | Advisory top-level turn budget; used for subagent turn caps |
| `timeout_s` | Hard wall-clock limit for the run |
| `max_tool_calls` | Optional hard tool-admission budget; nonnegative integer |
| `auto_confirm` | Auto-approve permission requests by default |
| `audit_requests` | Capture actual outgoing request metadata when enabled |
| `client_mode` | `copilot-cli` by default; `empty` disables ambient configuration and persona injection |
| `extra_config` | SDK settings not exposed as direct fields; overrides subject to validation |

### Limits and permissions

`max_turns` is not a hard top-level limit. Use `timeout_s` and, where appropriate,
`max_tool_calls` to bound execution. Tool admission does not prove a tool
completed or the application operation succeeded.

`auto_confirm=True` is convenient for deterministic tests, but it is not an
isolation boundary. Restrict tools and use guarded adapters and an approved
execution environment. A temporary working directory alone does not prevent
filesystem or network access.

### One attempt per call

Each `copilot_eval` call makes one execution attempt. Startup, connection, and
task failures are recorded without automatically starting another session.
Rerun a selected pytest case explicitly when appropriate.

## Explicit skills and empty mode

Nonempty `skill_directories` set the public SDK `enable_skills=True` by default.
`enable_config_discovery` remains false. In empty mode, personal/project discovery,
custom instructions, file hooks, managed settings, and persona injection stay
disabled. Explicit tools and system prompt content remain supported.

Explicit directories combined with `extra_config={"enable_skills": False}` are
rejected, not silently ignored. `None` leaves the explicit-skills default enabled.
An empty directory list plus `enable_skills=False` is allowed. Use `disabled_skills`
to deliberately disable named skills within an otherwise loaded set.

Every requested directory must contain a valid `SKILL.md` or immediate child
skill directories. Relative paths use the Python caller's current directory.
Validation and public SDK discovery run before the task is sent; setup failure
is recorded as an execution error with no model send. SDK metadata and diagnostics
are available as `result.skill_discovery` and in native JSON, separately from reads.
See [Skills](../getting-started/skills.md) for input and evidence details.

## MCP server mappings

Attach servers directly to `CopilotEval(mcp_servers={...})`.

SDK configuration discovery is disabled by default. Personal or ambient MCP
configuration is not automatically attached to eval sessions. Supply servers,
skills, and custom agents explicitly, or use the configuration loaders for the
project under test.

To test SDK discovery deliberately, opt in:

```python
agent = CopilotEval(
    name="configuration-discovery",
    extra_config={"enable_config_discovery": True},
)
```

This opt-in can expose machine-specific tools and configuration; avoid it in
tests intended to be reproducible across developer machines and CI.

For example, attach the bundled Banking server over stdio:

```python
import sys

BANKING_MCP = {
    "banking": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
        "tools": ["*"],
    }
}
```

Remote transports use the same mapping:

```python
REMOTE_MCP = {
    "crm": {
        "type": "http",
        "url": "https://mcp.example.com/mcp",
        "headers": {"Authorization": "Bearer ${CRM_TOKEN}"},
        "tools": ["*"],
    }
}
```

## CLI process configuration

`CLIServer` configures a lower-level CLI wrapper. It is not a `CopilotEval`
configuration and does not take `name`:

```python
from pytest_skill_engineering import CLIServer


server = CLIServer(command="git", tool_prefix="git")
```

With `shell="none"`, the command runs directly without a shell. Single or double
quotes group words and are removed before execution. Windows base commands keep
backslashes as path separators, including unquoted paths; other platforms use
POSIX escaping. Tool-supplied arguments use POSIX quoting on every platform.

## pytest configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = """
--aitest-json=aitest-reports/results.json
"""
```

`pytest-skill-engineering init` adds these settings to an existing
project. It reports conflicting values instead of replacing them.

## Related references

Use [CLI options](cli.md) for repetition and evidence flags,
[CopilotResult](result.md) for returned fields, and
[assertions](assertions.md) for independent output checks. Saved evidence requires
the current schema exactly; loading it does not execute a model.
