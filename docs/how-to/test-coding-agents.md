---
description: "Run a verified coding task and configure isolation, budgets, guarded tools, and request audits."
---

# Test skills and custom agents

Run a representative task with `CopilotEval` and verify its actual output.
Use skills or custom agents only when they are part of the interface you want
to test. The framework manages sessions, controls, usage, and evidence; your
fixtures own application state, guarded adapters, and independent verification.

## Quick start

This complete test verifies generated Python syntax without executing
untrusted generated code:

```python
from __future__ import annotations

import ast

from pytest_skill_engineering.copilot import CopilotEval


async def test_creates_module(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="calculator-module",
        model="gpt-5.6-sol",
        instructions="Create the requested Python module.",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent, "Create calculator.py with functions add(a, b) and subtract(a, b)."
    )

    assert result.success, result.error
    tree = ast.parse((tmp_path / "calculator.py").read_text(encoding="utf-8"))
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"add", "subtract"} <= functions
```

This checks syntax and function presence, not arithmetic correctness. Add
independent behavior tests in an environment approved for executing generated
code. A model's statement that its tests passed is not independent verification.

## Core CopilotEval fields

| Field | Use |
|---|---|
| `instructions` | Set the system prompt; the user task goes to `copilot_eval` |
| `working_directory` | Choose the workspace; this is not a security sandbox |
| `model` / `reasoning_effort` | Choose an accessible model and supported effort |
| `timeout_s` | Bound execution wall time, including startup |
| `max_tool_calls` | Cap admitted tool calls; `None` means no cap |
| `allowed_tools` / `excluded_tools` | Configure runtime tool lists |
| `skill_directories` | Load and validate explicit skills |
| `custom_agents` | Supply custom agent definitions |

`max_turns` is advisory for the top-level session, not a hard tool-call or
wall-clock limit. Permissions are auto-approved by default (`auto_confirm=True`);
provide appropriate guards and test-only resources.

## Result helpers

Use `file()`, `file_exists()`, and `files_matching()` to inspect workspace output.
Use `tool_calls_for()`, `tool_was_called()`, and `tool_was_called_with()` to
inspect observed calls. `subagent_invocations` records dispatch.

`success` describes session completion. `final_response` may be `None`.
Check `error`, `stop_reason`, `capture_errors`, and `evidence_complete` before
interpreting a trace. Tool presence, a file's existence, and a completion claim
are not substitutes for checking the required output.

## Isolated, bounded benchmarks

For a controlled application task, explicitly supply guarded SDK tools and
exclude inherited configuration. This **illustrative test** requires your
`guarded_tools` and `application` fixtures:

```python
from pytest_skill_engineering.copilot import CopilotEval


async def test_application_task(copilot_eval, record_property, guarded_tools, application):
    agent = CopilotEval(
        name="guarded-application",
        model="gpt-5.6-sol",
        instructions="Complete the task using only the supplied tools.",
        system_message_mode="replace",
        client_mode="empty",
        reasoning_effort="medium",
        timeout_s=600,
        max_tool_calls=80,
        image_detail="high",
        audit_requests=True,
        allowed_tools=[tool.name for tool in guarded_tools],
        extra_config={"tools": guarded_tools},
    )
    result = await copilot_eval(agent, "Save the application document with the required values.")
    observed = await application.read_saved_document()
    passed = observed == application.expected_document
    record_property("verification", {"observed": observed, "passed": passed})

    assert result.success, result.error
    assert result.evidence_complete, result.capture_errors
    assert passed
```

`guarded_tools` returns SDK `Tool` objects with handlers; there is no
framework-specific tool wrapper. Your application fixture initializes state,
owns any exclusive application lock, and independently reads saved output.
Record only JSON-compatible, non-sensitive observations.

### Isolation and budgets

`client_mode="empty"` uses framework-owned runtime storage and disables ambient
configuration, custom instructions, file hooks, and managed settings. It skips
persona injection and defaults to no available tools. Explicit skills can
still be loaded. This isolates configuration, not the machine or network.

`max_tool_calls=80` admits at most 80 calls after caller pre-tool guards. The
next attempted call is denied and aborts the session with
`stop_reason="tool_budget_exceeded"`. Zero permits no calls. The cap applies to
the current session, not independently created sessions.
`tool_calls_admitted` counts admissions; permissions can still deny a call.

Each `copilot_eval` call makes one attempt. Startup, connection, timeout, and
budget failures are not silently retried. Rerun selected pytest cases
explicitly after investigation.

### Cleanup and application safety

On timeout or a budget stop, the framework closes dispatch, aborts the session,
and drains running custom handlers before returning. Draining can exceed
`timeout_s`: cleanup safety takes precedence over starting another task.

Handlers must await all work they start. Cancelling a local MCP request does
not prove a remote action stopped. Adapters must track and drain remote work
before releasing an application lock or closing the application. Do not launch
untracked background input from a handler.

Caller and persona pre-tool guards are retained; a denial cannot be overridden
by an allow decision. Caller permission handlers are not replaced by automatic
approval. Conflicting non-pre-tool hooks fail explicitly.

### Image controls and request audits

`image_detail="high"` rewrites outgoing OpenAI image content before HTTP or
WebSocket dispatch; `None` leaves it unchanged. `audit_requests=True` records
observed outgoing model, tool names, reasoning effort, image details, and system
prompt hash. These settings leave the SDK's transport selection and caller
`capi` options unchanged.

Auditing supports HTTP OpenAI Responses and Chat Completions requests, plus
WebSocket Responses `response.create` text messages with function tools.
Every outgoing WebSocket message is checked, including continuations.
Requests with `previous_response_id` must explicitly include model,
instructions, tools, and input; missing settings are rejected rather than
reconstructed.

Unsupported frames, binary frames, provider schemas, malformed requests, and
runs with no observed request fail explicitly. A WebSocket transport error
blocks subsequent inference forwarding rather than retrying over HTTP.
Do not disable auditing just to turn a control failure into an apparent pass.

The audit stores no raw messages, image bytes, credentials, URLs, or headers.
Ordinary native evidence still contains conversation and tool output, which
can contain sensitive application data. Audited transport shutdown precedes
SDK-client shutdown.

### Offline control regression

The repository's runtime regression uses a loopback WebSocket server and an
in-memory image tool. Set `PYTEST_COPILOT_RUNTIME_PATH` to an already-cached
runtime executable, then run:

```bash
uv run python -m pytest tests/unit/test_request_websocket_runtime.py -q -o addopts=
```

Without the explicit path, it skips rather than downloading a runtime. It
checks continuations, image rewriting, budgets, transport failures, and timeout
cleanup without credentials, live model calls, or desktop input. It proves
control behavior, not model performance or live transport selection.

### Save application verification

For your authorized task suite:

```bash
uv run python -m pytest tests/benchmarks -o addopts= --aitest-json=results/native.json --junitxml=results/junit.xml
```

This command is illustrative: supply your own test path. Use a fresh persistent
output destination. `record_property` values are saved as name/value pairs in
`tests[].properties`; audits, usage, and stop information are in `eval_result`.
Stop further application trials on setup, transport, audit, or cleanup failure.
A timeout or tool-budget stop is a failed task.

## Custom agents

Load `.agent.md` definitions with `load_custom_agent()` or
`load_custom_agents()` and supply `custom_agents`. Check dispatch through
`result.subagent_invocations` and the task output separately.

See [Custom agents](../getting-started/custom-agents.md) for a definition,
completed-dispatch check, and child evidence.

## Testing skills

Supply `skill_directories=["skills/my-skill"]` and any tools the task needs.
Inspect `skill_discovery` for runtime availability, observed reads for usage,
and actual artifacts for correctness.

See [Skills](../getting-started/skills.md) for local preflight and an artifact
test. Use [Comparing configurations](../getting-started/comparing.md) to
investigate a change with fixed criteria.

## Authentication

Authenticate locally with `gh auth login --hostname github.com`, or supply an
authorized `GITHUB_TOKEN` or `GH_TOKEN`. The runtime selects `GITHUB_TOKEN`
first, then `GH_TOKEN`, then the signed-in SDK user. The selected account needs
Copilot access.

## Models

The starter uses `gpt-5.6-sol`. Check availability with
`uv run pytest-skill-engineering doctor`; configure another accessible model
explicitly when your task requires it. Live tests may consume premium requests.
See [Cost estimation](cost-estimation.md) before running a case matrix.
