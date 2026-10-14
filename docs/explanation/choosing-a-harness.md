---
description: "Choose a concrete question about your tools or instructions before designing a Copilot test."
---

# Choosing what to test

Start with a representative user task and a result you can verify. Then choose
the interface feature whose effect you want to observe.

| Your question | Configure or vary | Verify |
| --- | --- | --- |
| Can Copilot use my MCP server correctly? | `mcp_servers` and tool descriptions/schemas | Operation output or resulting application state |
| Can it use my CLI? | A guarded CLI tool adapter | Exit status, output, and resulting files/state |
| Do behavioral instructions help? | `instructions` | The same task output under both configurations |
| Does domain guidance help? | `skill_directories` | Skill availability/read evidence and independent task checks |
| Does it route to the right custom agent? | `custom_agents` and dispatch settings | Runtime invocation evidence and the actual result |
| Is user phrasing ambiguous? | The prompt sent to `copilot_eval` | Correct output for each representative phrasing |
| Does a different model meet my needs? | `model` | Fixed output checks, repeated observations, and recorded usage |

All of these use `CopilotEval` and the `copilot_eval` fixture. There is no
separate runner to choose.

## Start with one question

Use one supported model and one small task before adding a comparison. Pin the
model when consistency matters, and confirm its availability with `doctor`.
More configurations mean more paid execution, not necessarily more useful
evidence.

When comparing, change one factor, reset the starting state, and keep the
checks fixed. See [comparing configurations](../getting-started/comparing.md).
Tool selection, skill reads, and custom agent dispatch describe the execution;
none replaces checking the task's output.
