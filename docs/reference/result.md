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
| `stop_reason` | `completed`, `tool_budget_exceeded`, `timeout`, `request_audit_error`, `execution_error`, or `cleanup_error`; `None` for a result not finalized by the runner |
| `tool_calls_admitted` | Calls admitted by the framework after caller guards; not proof of execution or application success |
| `request_audit` | Actual outgoing request records when `audit_requests=True` |

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

`result` is the SDK's complete text representation, not necessarily one JSON
document. Current string-returning MCP tools include display text followed by a
structured `{"result": ...}` representation. Parse the known tool contract and
verify both agree; do not discard unexplained trailing data or invent a missing
payload. The bundled starter demonstrates this explicitly.

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
```

Tool-returned images are available on individual tool calls as `image_content`
(bytes) and `image_media_type`. See [Tool-returned images](../how-to/image-assertions.md).

## Token helpers

```python
result.total_input_tokens
result.total_output_tokens
result.total_tokens
result.token_usage
```

Each `usage` entry retains `model`, `input_tokens`, `output_tokens`,
`cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`,
`reasoning_effort`, and `duration_ms`. Missing SDK values are `None`, not zero.
Token totals are `None` when any corresponding count is unavailable (or no
usage was captured); `token_usage` omits those totals. Known zero remains zero.
Cost is an estimate from reported input/output counts, not a claim of complete
billing evidence; unknown cache reads receive no cache discount in that estimate.

## Request audit

Each `request_audit` record contains:

| Field | Meaning |
|---|---|
| `request_id` | SDK request identity |
| `model` | Actual model identifier in the outgoing body |
| `tool_names` | Function tool names advertised in that request, in order |
| `reasoning_effort` | Actual request effort, or `None` if absent |
| `image_details` | Detail on each outgoing image, in order; absent detail remains `None` |
| `image_count` | Number of observed images in that request |
| `instructions_sha256` | SHA-256 of actual system/developer text joined in order with two newlines, UTF-8 encoded |

For Responses requests the top-level `instructions` precedes system/developer
messages; text blocks within a message are also joined with two newlines.
An empty instruction sequence hashes the empty string. This hash is calculated
from the final outgoing request, not from `CopilotEval.instructions`.

For WebSocket Responses, there is one record per validated outgoing `response.create`
message. `request_id` is the SDK's connection identifier, so it repeats when
messages share a connection. Images count only those transmitted in that
message, not earlier images referenced through `previous_response_id`.
Continuation settings must be explicit; omitted settings are not copied from
earlier records. Unsupported messages are rejected before forwarding and add
no audit record.

The native JSON result preserves `request_audit`, `stop_reason`, `usage`,
`tool_calls_admitted`, and capture completeness, including failed runs. Custom
tool configuration records include names, descriptions, parameter schemas, and
metadata but never handler callbacks. Cleanup events are captured before the
final result is built. A cleanup failure takes precedence as `cleanup_error`;
the original timeout or budget error remains in `error`.

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
