---
description: "Load a plugin or project configuration into a CopilotEval."
---

# Plugin Testing

Use `CopilotEval.from_plugin()` when a task needs a bundle of instructions,
skills, custom agents, and MCP server definitions. The loader assembles
configuration; your test verifies what Copilot produces with it.

## What Is a Plugin?

The loader accepts these layouts:

| Input | What to pass |
|---|---|
| Manifest bundle | A directory containing `plugin.json` |
| GitHub configuration | The `.github/` directory, or a project root with `.github/agents/` |
| Claude configuration | A `.claude/` directory, or a root containing `CLAUDE.md` or `.claude/` |

These are loader formats, not a promise to reproduce an editor's entire plugin
runtime. The execution still uses GitHub Copilot.

## Quick Example

This test requires your own plugin at `plugins/my-plugin`:

```python
import json

from pytest_skill_engineering.copilot import CopilotEval


async def test_plugin_writes_json(copilot_eval, tmp_path):
    agent = CopilotEval.from_plugin(
        "plugins/my-plugin",
        model="gpt-5.6-sol",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, 'Write hello.json containing exactly {"message": "hello"}.')

    assert result.success, result.error
    assert json.loads((tmp_path / "hello.json").read_text(encoding="utf-8")) == {"message": "hello"}
```

This checks one artifact, not every component in the bundle. Add tasks that
exercise the components you intend to test.

## What Gets Loaded

`load_plugin(path)` lets you inspect the loaded instructions, `Skill` objects,
custom agent definitions, MCP configuration, hooks, and extension paths.
`from_plugin()` wires instructions, skills, agents, and MCP servers into the eval.
Loaded hook definitions and extension paths are **not** automatically executed.

Discovery differs by layout. In particular, the generic GitHub directory loader
does not read a project-root `.mcp.json`; supply `mcp_servers` explicitly when
needed. See [How to test plugins](../how-to/test-plugins.md) for exact layouts,
overrides, and verification patterns.

## Next Steps

- [Custom agents](custom-agents.md): test individual definitions.
- [Skills](skills.md): validate and load skill directories.
- [API reference](../reference/api.md): inspect public loader types.
