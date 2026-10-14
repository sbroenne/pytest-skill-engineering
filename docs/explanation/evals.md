---
description: "Separate session configuration from the user task and the output checks."
---

# Session configuration with CopilotEval

`CopilotEval` is the configuration for a real GitHub Copilot session. It is not
the task, the output checker, or the interface being tested.

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="file-writing",
    instructions="Save the files the user requests.",
    timeout_s=120,
)
```

An async pytest test sends its task separately:

```python
result = await copilot_eval(agent, "Write status.txt containing exactly Ready.")
```

Then the test checks the saved file. `result.success` alone checks execution,
not the file's contents.

## Three separate decisions

| Part | What it controls |
| --- | --- |
| `CopilotEval` | Model, system prompt, tools, skills, custom agents, working directory, and limits |
| Prompt passed to `copilot_eval` | The user's requested task |
| pytest assertions | The observable criteria for a correct result |

`instructions` supplies the system prompt. A prompt file can supply the user
task, but its contents must be loaded and passed to `copilot_eval`; it is not
another `CopilotEval` field. See the [configuration reference](../reference/configuration.md)
for supported settings.

## What you compare

Create separate configurations to compare a model, system prompt, skill, custom
agent definition, or MCP server variant. Keep the other settings, task, starting
state, and output checks fixed. Changing several at once makes a difference
harder to explain.

The framework supports GitHub Copilot, not interchangeable provider runners.
The meaningful choice is [what to test](choosing-a-harness.md), not which
framework harness to use.

## Identifying runs

Use `name` to label the configuration in saved evidence. pytest parameter IDs,
the observed model, and captured settings distinguish runs even when names
are reused.

## One attempt per execution

Each `copilot_eval` call makes one attempt. Startup, connection, and task failures
remain visible; the framework does not start replacement sessions. Rerun a
selected pytest case explicitly after investigating a failure.

Use [repetitions](../getting-started/iterations.md) to observe variation under
fixed criteria, not to retry until a failure disappears.
