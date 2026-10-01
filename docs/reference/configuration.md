---
description: "Configure CopilotEval, MCP servers, execution controls, and JSON evidence."
---

# Configuration

## Authentication

Supported authentication paths:

- `gh auth login --hostname github.com`
- `GITHUB_TOKEN` or `GH_TOKEN` in CI or automation

Eval sessions select `GITHUB_TOKEN` first, then `GH_TOKEN`. If neither
is set, the SDK uses its signed-in user. Tokens must authorize the intended
GitHub account and Copilot access.

No separate provider classes or third-party provider auth configuration is required.

## CopilotEval

```python
from pytest_skill_engineering.copilot import CopilotEval


agent = CopilotEval(
    name="banking-default",
    model="gpt-5.6-sol",
    instructions="Use the banking tools before answering.",
    mcp_servers={},
    allowed_tools=None,
    custom_agents=[],
    skill_directories=[],
    working_directory=None,
    max_turns=5,
)
```

### Important fields

| Field | Meaning |
|---|---|
| `name` | Label identifying the configuration in saved evidence |
| `model` | Copilot model name such as `gpt-5.6-sol` |
| `instructions` | System prompt content |
| `mcp_servers` | Copilot SDK server config mapping |
| `allowed_tools` | Optional global tool allow-list |
| `custom_agents` | Loaded `.agent.md` definitions |
| `skill_directories` | Explicit individual skill directories or parents; enable loading and check SDK availability before sending |
| `disabled_skills` | Skill names deliberately disabled, retained in discovery evidence |
| `max_turns` | Advisory top-level turn budget; used for subagent turn caps |
| `timeout_s` | Hard wall-clock limit for the run |

Each `copilot_eval` call makes one execution attempt. Startup, connection, and
task failures are recorded without automatically starting another session.
Rerun a selected pytest case explicitly when appropriate.

### Explicit skills and empty mode

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

## MCP server config shape

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

## CLIServer helper

`CLIServer` is a lower-level wrapper and does not take `name=`:

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

## Notes

- Use Copilot model names only
- use only documented `CopilotEval` fields and pytest options
- evidence loading expects the current JSON schema exactly
- reading saved evidence never starts a model session
- ordinary pytest assertions and consumer-owned checks determine task correctness
