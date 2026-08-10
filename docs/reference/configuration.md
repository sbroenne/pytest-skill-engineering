---
description: "Configure CopilotEval, MCP servers, report output, and assertion models using the current Copilot-only APIs."
---

# Configuration

## Authentication

Supported authentication paths:

- `gh auth login`
- `GITHUB_TOKEN` in CI or automation

No separate provider classes or third-party provider auth configuration is required.

## CopilotEval

```python
from pytest_skill_engineering.copilot import CopilotEval


agent = CopilotEval(
    name="banking-default",
    model="gpt-5.4-mini",
    instructions="Use the banking tools before answering.",
    mcp_servers={},
    allowed_tools=None,
    custom_agents=None,
    skill_directories=None,
    working_directory=None,
    max_turns=5,
    max_retries=2,
)
```

### Important fields

| Field | Meaning |
|---|---|
| `name` | Human-readable report label |
| `model` | Copilot model name such as `gpt-5.4-mini` |
| `instructions` | System prompt content |
| `mcp_servers` | Copilot SDK server config mapping |
| `allowed_tools` | Optional global tool allow-list |
| `custom_agents` | Loaded `.agent.md` definitions |
| `skill_directories` | Skill packages to inject |
| `max_turns` | Session turn limit |
| `max_retries` | Retry count for transient runtime failures; default `2` |

## MCP server config shape

Attach servers directly to `CopilotEval(mcp_servers={...})`.

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
        "transport": "streamable-http",
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

## pytest configuration

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.4-mini
--aitest-html=aitest-reports/report.html
--llm-model=copilot/gpt-5.4-mini
"""
```

## Notes

- Use Copilot model names only
- use only documented `CopilotEval` fields and pytest options
- report regeneration expects the current JSON schema exactly
