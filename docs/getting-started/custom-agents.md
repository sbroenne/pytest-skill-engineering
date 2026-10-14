---
description: "Load custom agent definitions and check runtime dispatch separately from task output."
---

# Custom agents

Load `.agent.md` definitions through `custom_agents` to test custom agent
dispatch. A **custom agent** is a definition, not inherently a subagent.
`result.subagent_invocations` records actual runtime invocations.

## Load one custom agent

For example, create `.github/agents/writer.agent.md`:

```markdown
---
name: writer
description: Write requested JSON artifacts.
---

Write the requested JSON file in the working directory.
Use exactly the fields and values requested.
```

Then load it:

```python
from pytest_skill_engineering import load_custom_agent
from pytest_skill_engineering.copilot import CopilotEval

writer = load_custom_agent(".github/agents/writer.agent.md")
agent = CopilotEval(
    name="orchestrator",
    model="gpt-5.6-sol",
    instructions="Delegate JSON file-writing tasks to the writer custom agent.",
    custom_agents=[writer],
)
```

Standalone, plugin, and project loaders retain declared names and supported
settings: model, tools, reasoning effort, inference settings, skills, and
`mcp-servers`. Missing names use the filename. An explicit empty tool list
stays empty; duplicate resolved names are errors.

## Assert on runtime custom agent dispatch

With the definition above, this test checks both dispatch and the artifact:

```python
import json
from dataclasses import replace


async def test_dispatches_to_writer(copilot_eval, tmp_path):
    config = replace(agent, working_directory=str(tmp_path))
    result = await copilot_eval(
        config, 'Ask writer to create answer.json containing exactly {"total": 5}.'
    )

    assert result.success, result.error
    assert any(
        invocation.name == "writer" and invocation.status == "completed"
        for invocation in result.subagent_invocations
    )
    assert json.loads((tmp_path / "answer.json").read_text(encoding="utf-8")) == {"total": 5}
```

An observed invocation alone does not prove task correctness. For a review
agent, for example, verify the expected findings against a known fixture rather
than asserting that a review was dispatched.

Invocation statuses include `selected`, `started`, `completed`, and `failed`.
Framework-owned invocations retain a child `result` with its own conversation,
tools, usage, and capture errors. See
[Child execution evidence](../reference/result.md#child-execution-evidence).

Each nested invocation gets the remaining registry without its own definition.
The registry shrinks along the dispatch path, preventing dispatch back to
itself or an ancestor. Siblings can use definitions available in their
parent's registry.

## Load a directory of custom agents

```python
from pytest_skill_engineering import load_custom_agents

specialists = load_custom_agents(
    ".github/agents",
    exclude={"orchestrator"},
    overrides={"writer": {"model": "gpt-5.6-sol"}},
)
```

The directory loader reads immediate `.agent.md` files. Include/exclude filters
and per-agent overrides use resolved names, including declared names.

## Compare custom agent variants

Parametrize tests over definition files, load each with `load_custom_agent()`,
and apply the same dispatch and output checks. Keep the task, parent model,
tools, state, and limits fixed. A variant's declared child model or tools are
part of the configuration being compared.

Use [Comparing configurations](comparing.md) for separate pytest outcomes or
paired `ab_run` evidence. Neither session completion nor dispatch events
automatically assess the quality of the agent's work.
