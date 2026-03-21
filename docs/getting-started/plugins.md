---
description: Test complete plugin directories — instructions, skills, agents, and MCP servers — with a single function call.
---

# Plugin Testing

Test your GitHub Copilot CLI plugin or Claude Code project as a whole — not just individual tools.

## What Is a Plugin?

A plugin is a directory containing instructions, skills, custom agents, and MCP server configurations that work together. Instead of testing each piece separately, plugin testing loads everything and validates the combined behavior.

**Supported layouts:**

| Format | Key File | Example |
|--------|----------|---------|
| Plugin manifest | `plugin.json` | VS Code Copilot extensions |
| GitHub project | `.github/copilot-instructions.md` | Repos with Copilot customization |
| Claude project | `CLAUDE.md` or `.claude/` | Claude Code workspaces |

## Quick Example

```python
from pytest_skill_engineering import Eval, Provider

async def test_my_plugin(eval_run, my_mcp_server):
    agent = Eval.from_plugin(
        "path/to/my-plugin",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[my_mcp_server],
    )
    result = await eval_run(agent, "What can you help me with?")
    assert result.success
```

Or with the Copilot SDK:

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_my_plugin(copilot_eval, tmp_path):
    agent = CopilotEval.from_plugin(
        "path/to/my-plugin",
        model="gpt-5-mini",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, "Create a hello world script")
    assert result.success
```

## What Gets Loaded

`load_plugin()` auto-discovers and loads:

- **Instructions** — `copilot-instructions.md`, `CLAUDE.md`, or from `plugin.json`
- **Skills** — Markdown files with YAML frontmatter from skill directories
- **Custom agents** — `.agent.md` files from agent directories
- **MCP configs** — Server configurations from `plugin.json` or `.mcp.json`
- **Hooks** — Lifecycle hook definitions (if present)

## Next Steps

- [How to Test Plugins](../how-to/test-plugins.md) — Comprehensive guide with all options
- [Custom Agents](custom-agents.md) — Testing individual agent files
- [API Reference](../reference/api.md) — Full Plugin type documentation
