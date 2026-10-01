---
description: "CopilotEval is the public harness for testing GitHub Copilot against your tools, system prompts, skills, and custom agents."
---

# CopilotEval

`CopilotEval` is the public execution harness.

It defines:

- the **system prompt** (`instructions=`)
- the **model** (`model=`)
- the **tool surface** (`mcp_servers=`, `allowed_tools=`)
- the **custom agents** (`custom_agents=`)
- the **prompt files** you choose to send as user prompts
- execution limits such as `timeout_s` and `max_tool_calls`

## Why one harness

The project is intentionally Copilot-only. That keeps the runtime, reports, and documentation aligned with the real GitHub Copilot experience.

## What you compare

Create multiple `CopilotEval` instances when you want to compare:

- model choices
- system prompts
- skill directories
- custom agents
- MCP server variants

Keep the task, fixture state, and concrete output checks fixed. The framework
records each execution and its pytest outcome; your coding agent interprets
the observations. It does not generate rankings or select a winner.

## Identifying runs

Use `name=` to label the configuration in saved evidence. Genuine pytest
parameter IDs, the model, and captured configuration distinguish runs even when
the same runtime name is reused.

## One attempt per execution

Startup, connection, and task failures remain visible in the returned result.
The framework does not automatically start another session. Request an explicit
pytest rerun when appropriate; use repetitions to measure variation with fixed
criteria, not to hide failed attempts.
