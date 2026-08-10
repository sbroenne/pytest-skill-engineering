---
description: "There is one public harness now: CopilotEval. Choose what to vary around it instead of choosing between legacy harnesses."
---

# Choosing a test harness

There is one public harness: `CopilotEval`.

The useful choice is not between multiple harness implementations anymore. The useful choice is **what you vary around CopilotEval**.

## Vary the tool surface

Use `mcp_servers={...}` and `allowed_tools=[...]` to test server descriptions, schemas, and tool selection.

## Vary the system prompt

Change `instructions=` when you want to test system prompt behavior.

## Vary the custom agents

Attach `.agent.md` definitions with `custom_agents=[...]` when you want to test custom agent dispatch.

## Vary the prompt

Use the user message you send into `copilot_eval(...)` to test realistic task phrasing.

## Vary the model carefully

Start with `gpt-5.4-mini`.
Only add more expensive models when the extra comparison answers a real product question.
