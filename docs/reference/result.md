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
| `evidence_complete` | Every observed tool call has a correlated completion, known tool outcome, and captured output, error, or image |
| `capture_errors` | Missing or conflicting call records detected while mapping SDK events |

`success` describes session execution, not whether the application did the right
thing. A tool can fail and the session can recover. Check application state with
ordinary pytest assertions, and check `evidence_complete` separately. A model's
claim that it saved a file does not override a failed file assertion.

Missing completion, uncorrelated events, conflicting duplicate events, and
cancellation make session `success` false. A completed call whose output was not
captured makes `evidence_complete` false without changing the reported tool outcome.

## Captured tool evidence

Each item in `all_tool_calls` has these fields:

| Field | Meaning |
|---|---|
| `call_id` | SDK call identity; `None` means it was not captured |
| `completion_received` | `True`: completion observed; `False`: still pending; `None`: unknown |
| `success` | Tool completion outcome, or `None` when unknown |
| `result` | Captured text; `""` is genuinely empty output, `None` is no captured text |
| `error` | Captured tool error, if any |
| `evidence_complete` | Completion and outcome are known, and output, error, or image is present |

These are evidence checks, not an application verifier. They cannot prove that
events absent from the entire SDK stream ever occurred. Unmatched completions are
listed in `capture_errors`; their original events remain in `raw_events`, rather
than inventing a tool name or arguments. Normal duplicate events retain one call;
conflicting duplicates retain the first record and flag the conflict.

The existing `ToolCall` string representation is unchanged. Check
`evidence_complete` explicitly rather than using `repr()` as an evidence verdict.

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
