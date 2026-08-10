---
description: "CopilotResult reference: tool calls, responses, token usage, files, permissions, and runtime subagent events."
---

# CopilotResult

`copilot_eval(...)` returns a `CopilotResult`.

## Common fields

| Field | Meaning |
|---|---|
| `success` | Whether the eval completed successfully |
| `error` | Error message when `success` is false |
| `turns` | Normalized conversation turns |
| `usage` | Per-turn token usage entries |
| `model_used` | Actual Copilot model used |
| `total_premium_requests` | Premium-request accounting |
| `subagent_invocations` | Runtime subagent events from custom agent dispatch |
| `permission_requested` | Whether Copilot requested permissions |
| `raw_events` | Raw SDK events for advanced inspection |

## Response helpers

```python
result.final_response
result.all_responses
```

## Tool helpers

```python
result.tool_was_called("get_balance")
result.tool_call_count("get_balance")
result.tool_calls_for("get_balance")
result.tool_was_called_with("transfer", amount=500.0)
result.tool_images_for("screenshot")
```

## Token helpers

```python
result.total_input_tokens
result.total_output_tokens
result.total_tokens
result.token_usage
```

## File helpers

```python
result.working_directory
result.file("README.md")
result.file_exists("src/app.py")
result.files_matching("**/*.py")
```

## Custom agent dispatch terminology

A `.agent.md` file defines a **custom agent**.
`result.subagent_invocations` records the runtime **subagent** events that happen only if Copilot dispatches to that custom agent.
