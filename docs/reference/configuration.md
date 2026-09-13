---
description: "Configure CopilotEval, MCP servers, report output, and assertion models using the current Copilot-only APIs."
---

# Configuration

## Authentication

Supported authentication paths:

- `gh auth login --hostname github.com`
- `GITHUB_TOKEN` or `GH_TOKEN` in CI or automation

Eval and judge sessions select `GITHUB_TOKEN` first, then `GH_TOKEN`. If neither
is set, the SDK uses its signed-in user. Tokens must authorize the intended
GitHub account and Copilot access.

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
    custom_agents=[],
    skill_directories=[],
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
| `max_turns` | Advisory top-level turn budget; used for subagent turn caps |
| `timeout_s` | Hard wall-clock limit for the run |
| `max_retries` | Retry count for transient runtime failures; default `2` |

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
