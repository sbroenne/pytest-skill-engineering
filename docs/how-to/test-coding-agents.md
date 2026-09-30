---
description: "Test real GitHub Copilot coding sessions with CopilotEval, skills, prompt files, and custom agent dispatch."
---

# Test skills and custom agents

Use `CopilotEval` to run real GitHub Copilot sessions inside pytest. The interface,
skill, system prompt, or custom agent definition is under test, not the harness.
Session success and a file's existence are smoke checks; verify its actual
behavior too. pytest shows the checks' outcomes; JSON records execution for your
coding agent to investigate, without a separate judge or adviser.

## Quick start

```python
import pytest

from pytest_skill_engineering.copilot import CopilotEval


@pytest.mark.copilot
async def test_creates_module(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="coder",
        model="gpt-5.6-sol",
        instructions="Create production-quality Python code.",
        working_directory=str(tmp_path),
    )

    result = await copilot_eval(
        agent,
        "Create calculator.py with add, subtract, multiply, and divide.",
    )

    assert result.success
    assert result.file_exists("calculator.py")
```

## Core CopilotEval fields

```python
agent = CopilotEval(
    name="my-agent",
    model="gpt-5.6-sol",
    instructions="Your system prompt.",
    working_directory=str(tmp_path),
    max_turns=10,
    max_retries=2,
    excluded_tools=["run_in_terminal"],
    skill_directories=["./skills/my-skill"],
    custom_agents=[],
)
```

## Result helpers

- `result.success`
- `result.error`
- `result.final_response`
- `result.tool_was_called(...)`
- `result.tool_was_called_with(...)`
- `result.file(...)`
- `result.file_exists(...)`
- `result.files_matching(...)`
- `result.subagent_invocations`
- `result.total_premium_requests`

## Isolated, bounded benchmarks

Use the regular `copilot_eval` fixture, not a separate SDK runner. Application
fixtures own their tools and verify saved documents or other external state.
The framework owns model sessions, usage, evidence, and native reports.

```python
from pytest_skill_engineering.copilot import CopilotEval, HeadlessPersona


async def test_trial(copilot_eval, record_property, guarded_tools):
    record_property("route", "controls")
    agent = CopilotEval(
        name="controls",
        model="gpt-6-luna",
        instructions="Complete the task using only the supplied tools.",
        system_message_mode="replace",
        client_mode="empty",
        persona=HeadlessPersona(),
        reasoning_effort="medium",
        timeout_s=600,
        max_tool_calls=80,
        image_detail="high",
        audit_requests=True,
        max_retries=0,
        allowed_tools=[tool.name for tool in guarded_tools],
        extra_config={"tools": guarded_tools},
    )
    result = await copilot_eval(agent, "Complete the application task.")
    assert result.success, result.error
    assert result.evidence_complete
    # Also assert the application's actual output in this test.
```

`guarded_tools` is your fixture returning SDK `Tool` objects with handlers.
There is no framework-specific tool wrapper to implement.

| Setting | Behavior |
|---|---|
| `client_mode="empty"` | Owns temporary runtime storage, disables inherited configuration, instructions and file hooks, and skips persona injection. Defaults to no available tools unless explicitly supplied. |
| `max_tool_calls=80` | Admits at most 80 calls after caller pre-tool guards. The next attempted call is denied and the session is aborted with `tool_budget_exceeded`, rather than asking the model to keep trying. Zero permits no calls. |
| `image_detail="high"` | Rewrites actual outgoing OpenAI image content before HTTP or WebSocket dispatch. `None` leaves detail unchanged. |
| `audit_requests=True` | Records actual outgoing model, tool names, reasoning effort, image details and system prompt hash; unsupported requests fail rather than inventing evidence. |
| `max_retries=0` | Disables framework retries. Independently, failures after tool admission or observed tool activity are never retried. |

The normal defaults remain CLI mode, no tool-call limit, no image override, and
no request audit. `max_turns` remains advisory; it is not a tool-call limit.
The call cap applies to the current session, not independently created sessions.
`tool_calls_admitted` counts admissions, not verified application actions:
runtime permissions can still deny an admitted call.

The wall-clock limit includes startup and session creation. On timeout or a
budget stop, the framework closes dispatch, aborts the session, and waits for
already-running custom handlers **before returning**. Draining can exceed
`timeout_s`; safety takes priority over starting another trial. Handlers must
await all work they start. For remote MCP actions, cancellation of the local
request is not proof the action stopped: adapters must track and drain the
remote work before releasing their application lock or closing the application.
Never launch untracked background input from a handler.

Caller pre-tool guards are retained alongside persona pre-tool guards; denials
cannot be overridden by an allow decision. Caller permission handlers are not
replaced by automatic approval. Conflicting non-pre-tool hooks fail explicitly.

Request auditing supports HTTP OpenAI Responses and Chat Completions payloads,
and WebSocket Responses `response.create` text messages, with function tools.
The SDK's transport selection and caller `capi` options are left unchanged.
Auditing does not rely on the SDK's HTTP preference: consumer execution with
SDK 1.0.15 still selected WebSockets when that preference was supplied.

Every outgoing WebSocket message is checked and rewritten before forwarding,
including repeated requests on a persistent connection. Continuations with
`previous_response_id` must explicitly supply model, instructions, tools and
input; missing settings are rejected, not reconstructed from earlier messages.
Unsupported frames, binary frames, other provider schemas, malformed requests,
and runs with no observed request fail explicitly. WebSocket transport errors
also fail closed, blocking subsequent inference forwarding rather than silently
retrying over HTTP. Do not disable auditing to make a benchmark appear valid.
The audit stores no raw messages, image bytes, credentials, URLs, or headers.
Normal native reports still contain their ordinary conversation/tool evidence.

An offline regression runs the actual cached runtime through `copilot_eval`
against a loopback WebSocket server and an in-memory image tool. It covers
continuations, image rewriting, tool budgets, transport failure and timeout cleanup without
real credentials, model calls or desktop input. Set `PYTEST_COPILOT_RUNTIME_PATH`
to an already cached runtime executable, then run:

```powershell
uv run python -m pytest tests\unit\test_request_websocket_runtime.py -q -o addopts=""
```

Without that explicit path, the runtime regression is skipped rather than
downloading or launching an unspecified runtime. These checks validate control
behavior, not model performance or the live Copilot API's transport selection.

For a JSON-only benchmark, explicitly override
repository report defaults:

```powershell
uv run python -m pytest tests\benchmarks -o addopts="" --aitest-json=results\native.json --junitxml=results\junit.xml
```

Use a fresh persistent output directory. `record_property` values appear in
native JSON `tests[].properties` as name/value pairs as well as in JUnit.
Audit, usage and stop information are under `tests[].eval_result`. Stop the
remaining benchmark cases on setup, transport, audit, or cleanup failure;
a timeout or tool budget failure is a failed task, never a successful result.

## Custom agents

Attach loaded `.agent.md` definitions to test **custom agent dispatch**:

```python
from pytest_skill_engineering import load_custom_agent


reviewer = load_custom_agent(".github/agents/reviewer.agent.md")

agent = CopilotEval(
    name="orchestrator",
    model="gpt-5.6-sol",
    instructions="Delegate code review requests to the reviewer custom agent.",
    custom_agents=[reviewer],
)
```

The `.agent.md` file defines a **custom agent**. It becomes a **subagent** only when Copilot dispatches to it at runtime. Assert on those runtime events with `result.subagent_invocations`.

## Testing skills

```python
agent = CopilotEval(
    name="with-skill",
    model="gpt-5.6-sol",
    instructions="Use the available skills.",
    skill_directories=["skills/banking-advisor"],
)
```

## Authentication

Supported auth paths:

```bash
gh auth login
```

or `GITHUB_TOKEN` in CI.

## Models

Start with `gpt-5.6-sol` for routine tests. Add larger models only for targeted comparisons.
