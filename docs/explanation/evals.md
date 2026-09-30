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
- execution limits such as `max_turns` and `max_retries`

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

## Retries

`max_retries` defaults to `2`.
Retries are useful for transient Copilot session failures, not as a substitute for fixing deterministic tool or prompt problems.
