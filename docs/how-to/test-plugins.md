---
description: "Test complete plugin directories — instructions, skills, agents, and MCP servers — as a unified composition with pytest-skill-engineering."
---

# How to Test Plugins

Test GitHub Copilot CLI plugins and Claude Code projects as a whole. Plugin testing validates the full composition — instructions, skills, custom agents, and MCP servers working together — not just individual pieces.

## Why Plugin Testing?

Individual tool tests verify that one MCP server works in isolation. But real plugins combine multiple components:

- **Instructions** that set agent behavior
- **Skills** that inject domain knowledge
- **Custom agents** that handle specialized tasks
- **MCP servers** that provide tools

A plugin test loads everything from a directory and validates the combined behavior. If the instructions conflict with the skill, or a custom agent can't find the right tool, plugin testing catches it.

## Plugin Directory Layouts

pytest-skill-engineering auto-detects three directory formats:

| Format | Detection | Typical Use |
|--------|-----------|-------------|
| `plugin.json` manifest | `plugin.json` exists at root | VS Code Copilot extensions |
| `.github/` project | `copilot-instructions.md` exists in `.github/` | GitHub repos with Copilot customization |
| `.claude/` project | `CLAUDE.md` at root or `.claude/` directory | Claude Code workspaces |

### plugin.json (VS Code Extensions)

```
my-plugin/
├── plugin.json              # Manifest with name, instructions, MCP config
├── agents/
│   ├── reviewer.agent.md
│   └── writer.agent.md
└── skills/
    └── code-standards/
        └── SKILL.md
```

### .github/ Project (GitHub Repos)

```
my-project/
├── .github/
│   ├── copilot-instructions.md   # System prompt
│   └── agents/
│       ├── reviewer.agent.md
│       └── writer.agent.md
├── .mcp.json                      # MCP server configurations
└── skills/
    └── domain-knowledge/
        └── SKILL.md
```

### .claude/ Project (Claude Code)

```
my-project/
├── CLAUDE.md                # System prompt
├── .claude/
│   └── settings.json        # Claude-specific config
├── .mcp.json                # MCP server configurations
└── skills/
    └── domain-knowledge/
        └── SKILL.md
```

## Loading Plugins

Use `load_plugin()` to inspect a plugin directory before testing:

```python
from pytest_skill_engineering import load_plugin

plugin = load_plugin("path/to/my-plugin")

# Inspect what was discovered
print(plugin.metadata.name)      # Plugin name from manifest or directory
print(plugin.instructions)        # Merged instructions from all sources
print(plugin.agents)              # List of loaded .agent.md definitions
print(plugin.skills)              # Loaded Skill objects
print(plugin.mcp_configs)         # MCP server configurations from manifest
```

`load_plugin()` auto-detects the format based on directory contents and loads all components. Use this for programmatic inspection, or pass the path directly to `Eval.from_plugin()` / `CopilotEval.from_plugin()`.

## Testing with PydanticAI (Eval)

Use `Eval.from_plugin()` when testing MCP tool usage and system prompt behavior with a synthetic agent:

```python
import pytest
from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

@pytest.fixture(scope="module")
def banking_server():
    return MCPServer(
        command=["python", "-m", "my_banking_mcp"],
        wait=Wait.for_tools(["get_balance", "transfer"]),
    )

async def test_plugin_tool_usage(eval_run, banking_server):
    # Load plugin and override MCP servers with running instances
    agent = Eval.from_plugin(
        "path/to/my-plugin",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    result = await eval_run(agent, "What's my checking balance?")

    assert result.success
    assert result.tool_was_called("get_balance")
```

`Eval.from_plugin()` loads instructions, skills, and custom agents from the directory, then uses PydanticAI to execute the agent. Pass `mcp_servers=` to override MCP configs with real running server instances.

### Overriding Plugin Settings

```python
# Override the provider model
agent = Eval.from_plugin(
    "path/to/my-plugin",
    provider=Provider(model="azure/gpt-5.2-chat"),
    mcp_servers=[banking_server],
    max_turns=10,  # Override turn limit
)

# Override system prompt (ignores plugin instructions)
agent = Eval.from_plugin(
    "path/to/my-plugin",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
    system_prompt="Custom override instructions.",
)
```

## Testing with Copilot SDK (CopilotEval)

Use `CopilotEval.from_plugin()` when testing with the real GitHub Copilot agent — including custom agent dispatch, skill loading, and file operations:

```python
import pytest
from pytest_skill_engineering.copilot import CopilotEval

@pytest.mark.copilot
async def test_plugin_with_copilot(copilot_eval, tmp_path):
    agent = CopilotEval.from_plugin(
        "path/to/my-plugin",
        model="gpt-5-mini",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, "Create a hello world script")

    assert result.success
    assert (tmp_path / "hello.py").exists()
```

### Verifying Custom Agent Dispatch

When your plugin includes custom agents, verify that Copilot dispatches to the right one:

```python
@pytest.mark.copilot
async def test_plugin_routes_to_reviewer(copilot_eval, tmp_path):
    agent = CopilotEval.from_plugin(
        "path/to/my-plugin",
        model="gpt-5-mini",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, "Review this code for security issues")

    assert result.success
    invoked = [s.eval_name for s in result.subagent_invocations]
    assert "reviewer" in invoked
```

## Claude Code Projects

Use `CopilotEval.from_claude_config()` to test Claude Code project directories. This loads `CLAUDE.md` as the system prompt and `.claude/` settings:

```python
from pytest_skill_engineering.copilot import CopilotEval

@pytest.mark.copilot
async def test_claude_project(copilot_eval, tmp_path):
    agent = CopilotEval.from_claude_config(
        "path/to/claude-project",
        model="gpt-5-mini",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, "Explain this project")

    assert result.success
```

!!! note "Claude Config ≠ Claude Model"
    `from_claude_config()` loads the project's *configuration format* (CLAUDE.md, .claude/ settings). The agent still runs on whatever model you specify — typically a GitHub Copilot model.

## MCP Config Loading

Load MCP server configurations from `.mcp.json` files independently:

```python
from pytest_skill_engineering.copilot import load_mcp_config

configs = load_mcp_config("path/to/.mcp.json")
# Returns dict of server name → config

for name, config in configs.items():
    print(f"Server: {name}")
    print(f"  Command: {config.get('command')}")
    print(f"  Args: {config.get('args', [])}")
```

This is useful when you need to inspect MCP configurations without loading the full plugin, or when building custom test fixtures from a project's server definitions.

## Assertion Helpers

### Basic Assertions

```python
# Agent completed successfully
assert result.success

# Specific tool was called
assert result.tool_was_called("get_balance")

# Tool called at least N times
assert result.tool_call_count("transfer") >= 1

# Total tool calls
assert len(result.all_tool_calls) >= 2
```

### Multi-Server Assertions

When plugins have multiple MCP servers, assert which server handled a tool call:

```python
# Verify the tool came from the expected server
assert result.tool_was_called_from_server("get_balance", "banking-server")

# Useful when two servers expose similarly-named tools
assert result.tool_was_called_from_server("search", "document-server")
assert not result.tool_was_called_from_server("search", "web-server")
```

### Semantic Assertions

Use `llm_assert` for AI-powered validation of response content:

```python
async def test_plugin_response_quality(eval_run, llm_assert, banking_server):
    agent = Eval.from_plugin(
        "path/to/my-plugin",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    result = await eval_run(agent, "Summarize my financial situation")

    assert result.success
    assert llm_assert(
        result.final_response,
        "provides a summary of account balances with actionable advice",
    )
```

## SDK Passthroughs

`CopilotEval` supports additional SDK configuration for advanced scenarios:

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="my-test",
    model="gpt-5-mini",
    active_agent="banking-advisor",  # Route to a specific custom agent
    hooks={"onSessionStart": "path/to/hook.py"},  # Lifecycle hooks
    working_directory=str(tmp_path),
)
```

| Parameter | Description |
|-----------|-------------|
| `active_agent` | Route the session to a specific custom agent by name |
| `hooks` | Lifecycle hook configuration (dict of event → handler path) |
| `excluded_tools` | List of tool names to block from the agent |
| `skill_directories` | Directories containing skills to load |
| `reasoning_effort` | Reasoning effort level (`"low"`, `"medium"`, `"high"`) |
| `custom_agents` | List of custom agent definitions for subagent dispatch |

## Comparing Plugin Configurations

Parametrize tests to compare different plugin versions or configurations:

```python
from pathlib import Path

PLUGIN_DIRS = [
    "plugins/v1-minimal",
    "plugins/v2-with-skills",
    "plugins/v3-with-agents",
]

@pytest.mark.parametrize("plugin_path", PLUGIN_DIRS, ids=lambda p: Path(p).name)
async def test_plugin_versions(eval_run, banking_server, plugin_path):
    agent = Eval.from_plugin(
        plugin_path,
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    result = await eval_run(agent, "What's my checking balance?")

    assert result.success
    assert result.tool_was_called("get_balance")
```

The report generates an **eval leaderboard** comparing pass rates, costs, and AI-analyzed differences across plugin versions.

## Supported Formats Reference

| Format | Detection | Use With |
|--------|-----------|----------|
| `plugin.json` | File exists at root | `Eval.from_plugin()`, `CopilotEval.from_plugin()` |
| `.github/` project | `copilot-instructions.md` exists | `Eval.from_plugin()`, `CopilotEval.from_plugin()` |
| `.claude/` project | `CLAUDE.md` or `.claude/` dir exists | `CopilotEval.from_claude_config()`, `CopilotEval.from_plugin()` |

## Next Steps

- **[Test MCP Servers](test-mcp-servers.md)** — Deep dive into MCP server configuration and transports
- **[Test Coding Agents](test-coding-agents.md)** — Test real coding agents with the Copilot SDK
- **[Complete Example](complete-example.md)** — End-to-end test suite demonstrating all features
- **[Getting Started: Plugin Testing](../getting-started/plugins.md)** — Quick intro to plugin testing concepts
