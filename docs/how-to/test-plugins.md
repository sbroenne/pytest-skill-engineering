---
description: "Inspect a configuration bundle, load it into Copilot, and verify a task that exercises it."
---

# How to Test Plugins

Use `CopilotEval.from_plugin()` to run a task with a bundle of instructions,
skills, custom agents, and MCP server definitions. Inspect what the loader
found first, then choose a task and output checks that exercise the components
you care about.

## Why Plugin Testing?

A task may require several components to work together. For example, an
instruction can route a task to a custom agent that needs an MCP tool and a
skill's output schema. A test of that task can expose a composition failure.
Loading a directory or completing a session alone does not verify the bundle.

## Plugin Directory Layouts

The loader accepts these layouts:

| Input | Detection and discovery |
|---|---|
| Manifest bundle | `plugin.json` at the supplied directory root |
| GitHub config directory | Supplied directory named `.github` |
| GitHub project root | `.github/agents/` exists under the root |
| Claude config directory | Supplied directory named `.claude` |
| Claude project root | Root contains `CLAUDE.md` or `.claude/` |

Manifest detection takes precedence. A root with only
`.github/copilot-instructions.md` and no `.github/agents/` is not detected as a
GitHub plugin root; pass the `.github` directory or use
`CopilotEval.from_copilot_config(root)`.

### plugin.json (manifest bundles)

```text
my-plugin/
├── plugin.json
├── instructions.md
├── agents/
│   └── writer.agent.md
└── skills/
    └── invoice-format/
        └── SKILL.md
```

A minimal manifest:

```json
{
  "name": "invoice-plugin",
  "instructions": ["instructions.md"],
  "mcp_servers": {}
}
```

Manifest `instructions` contains paths, not inline instruction text. The loader
also reads root `copilot-instructions.md` and `CLAUDE.md` when present.
Agents and skills are discovered from their conventional subdirectories.

### .github/ Project (GitHub Repos)

```text
my-project/
└── .github/
    ├── copilot-instructions.md
    ├── agents/
    │   └── writer.agent.md
    └── skills/
        └── invoice-format/
            └── SKILL.md
```

The generic GitHub loader discovers these components from `.github/`. It does
not read a project-root `.mcp.json`. Supply `mcp_servers` explicitly if needed.

### .claude/ Project (Claude Code)

```text
my-project/
├── CLAUDE.md
├── .mcp.json
└── .claude/
    ├── CLAUDE.md
    ├── agents/
    │   └── writer.md
    └── skills/
        └── invoice-format/
            └── SKILL.md
```

Pass the **project root** to load the root instructions and `.mcp.json` along
with `.claude/` agents and skills. Passing only `.claude/` changes the discovery
root and does not include the parent project's files.

## Loading Plugins

Inspect your bundle without starting Copilot:

```python
from pytest_skill_engineering import load_plugin

plugin = load_plugin("plugins/my-plugin")
print(plugin.metadata.name)
print(plugin.instructions)
print([agent["name"] for agent in plugin.agents])
print([skill.name for skill in plugin.skills])
print(sorted(plugin.mcp_servers))
```

The public attribute is `plugin.mcp_servers`, not `mcp_configs`. Invalid files
and metadata raise errors; do not silently replace an invalid bundle with an
empty configuration.

`load_plugin()` also exposes hook definitions and extension paths.
`from_plugin()` does **not** automatically execute those hooks or extensions.
For lifecycle behavior, supply SDK-compatible hooks explicitly and verify them.

## Testing Plugins

This test requires your own bundle at `plugins/my-plugin`:

```python
from __future__ import annotations

import json

from pytest_skill_engineering.copilot import CopilotEval


async def test_plugin_output(copilot_eval, tmp_path, record_property):
    agent = CopilotEval.from_plugin(
        "plugins/my-plugin",
        model="gpt-5.6-sol",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent, 'Write answer.json containing exactly {"total": 5}.'
    )
    path = tmp_path / "answer.json"
    observed = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    record_property("verification", {"observed": observed, "passed": observed == {"total": 5}})

    assert result.success, result.error
    assert result.evidence_complete, result.capture_errors
    assert observed == {"total": 5}
```

This verifies the artifact. Tailor the task to your bundle's purpose; a generic
file task does not establish that a banking tool or review agent works.

### Overriding Plugin Settings

`model`, `name`, `working_directory`, and other eval fields can be supplied
explicitly. The factory's `instructions` argument **appends** to discovered
instructions; it does not replace them:

```python
agent = CopilotEval.from_plugin(
    "plugins/my-plugin",
    model="gpt-5.6-sol",
    instructions="Also keep the final reply brief.",
)
```

To replace the combined instructions deliberately:

```python
from dataclasses import replace

agent = replace(agent, instructions="Use only these replacement instructions.")
```

This is separate from `system_message_mode`, which controls whether the eval
instructions append to or replace Copilot's base system prompt.

## Testing with Copilot SDK (CopilotEval)

All task executions use GitHub Copilot. The loader selects `ClaudeCodePersona`
for `.claude` paths or roots containing `.claude/`, otherwise `VSCodePersona`,
unless you supply a persona. These provide supported runtime conventions, not
a complete editor or Claude Code runtime.

### Verifying Custom Agent Dispatch

For a bundle with a `writer` custom agent, add a dispatch requirement to an
artifact test:

```python
assert any(
    invocation.name == "writer" and invocation.status == "completed"
    for invocation in result.subagent_invocations
)
```

This fragment belongs after a task that explicitly requires dispatch. Keep the
artifact assertions too. Loaded definitions retain names and supported SDK
settings; duplicate resolved names are errors. See
[Custom agents](../getting-started/custom-agents.md) for child evidence.

## Claude Code Projects

Use `CopilotEval.from_claude_config(project_root)` for explicit Claude-format
project loading:

```python
agent = CopilotEval.from_claude_config(
    "projects/my-claude-project",
    model="gpt-5.6-sol",
)
```

It reads root and `.claude/CLAUDE.md`, `.claude/agents/*.md`,
`.claude/skills/`, and root `.mcp.json`. Its `instructions` argument also
appends. This loads a configuration format; it does not run Claude Code or
force a Claude model.

## MCP Config Loading

Load a server configuration independently:

```python
from pytest_skill_engineering.copilot import load_mcp_config

servers = load_mcp_config("projects/my-project/.mcp.json")
agent = CopilotEval(name="project-tools", mcp_servers=servers)
```

Inspect safe server names rather than printing commands, environment variables,
or headers that may contain secrets.

## Assertion Helpers

`tool_was_called()`, `tool_calls_for()`, `tool_call_count()`, and
`tool_was_called_with()` inspect captured calls. Use the exact runtime name,
including an MCP prefix when present. `CopilotResult` has no
`tool_was_called_from_server()` method.

Tool selection is a diagnostic or routing requirement, not independent output
verification. Assert concrete file content, returned operation data, or fixture
state, and save safe observations with `record_property`.

## SDK Passthroughs

Useful eval fields include:

| Field | Purpose |
|---|---|
| `active_agent` | Select a custom agent by name at session start |
| `custom_agents` | Supply loaded definitions |
| `skill_directories` | Load explicit skills |
| `allowed_tools` / `excluded_tools` | Configure SDK tool lists |
| `hooks` | Supply SDK `SessionHooks` handlers |
| `reasoning_effort` | Request a model-supported reasoning effort |
| `extra_config` | Supply other supported SDK session settings |

Hooks are typed SDK handlers, not a dictionary of event names to script paths.
Validate passthrough settings against your installed SDK; unsupported shapes
are not a portable example.

## Comparing Plugin Configurations

Parametrize over plugin paths and apply the same task, state, permissions,
limits, and independent checks. Record safe version identifiers. Each
parameter has its own pytest outcome; paired `ab_run` entries instead share
one outcome and require side-specific verification.

## Supported Formats Reference

See the [layout table](#plugin-directory-layouts) above for discovery roots.
Do not assume an arbitrary directory or an editor extension package is a
supported manifest bundle.

## Next Steps

- [Test MCP servers](test-mcp-servers.md): transports and completed operation data.
- [Test skills and custom agents](test-coding-agents.md): bounded application tasks.
- [Complete example](complete-example.md): a self-contained bundled-server test.
- [Plugin configuration](../getting-started/plugins.md): a short introduction.
