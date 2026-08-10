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

The report ranks them by pass rate first and cost second.

## Stable identity vs display names

Every eval needs a stable machine identity internally, but reports should display human-readable names.
Use `name=` for the display label users see in the report.

## Retries

`max_retries` defaults to `2`.
Retries are useful for transient Copilot session failures, not as a substitute for fixing deterministic tool or prompt problems.
