"""Offline checks of SDK boundaries; never start a model or a desktop tool."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
import pytest
from copilot import CopilotRequestContext
from copilot.session import PreToolUseHookOutput
from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.copilot.api import run_copilot
from pytest_skill_engineering.copilot.events import EventMapper
from pytest_skill_engineering.copilot.fixtures import _convert_to_aitest
from pytest_skill_engineering.core.serialization import serialize_dataclass


def event(name: str, **data: Any) -> Any:
    return SimpleNamespace(type=name, data=SimpleNamespace(**data))


def context() -> CopilotRequestContext:
    return CopilotRequestContext(
        request_id="request-1",
        session_id="session-1",
        transport="http",
        url="https://example.invalid/responses",
        headers={},
        cancel_event=asyncio.Event(),
    )


class FakeSession:
    session_id = "session-1"

    def __init__(self, config: dict[str, Any], behavior: Any) -> None:
        self.config = config
        self.behavior = behavior
        self.aborted = False

    async def send_and_wait(self, prompt: str, timeout: float) -> None:
        await self.behavior(self)

    async def abort(self) -> None:
        self.aborted = True

    async def dispatch(self, number: int) -> bool:
        hook = self.config["hooks"]["on_pre_tool_use"]
        decision = await hook(
            {
                "sessionId": self.session_id,
                "timestamp": datetime.now(timezone.utc),
                "workingDirectory": ".",
                "toolName": "act",
                "toolArgs": {"number": number},
            },
            {},
        )
        if decision and decision.get("permissionDecision") == "deny":
            return False
        self.config["on_event"](
            event("tool.execution_start", tool_call_id=str(number), tool_name="act", arguments={})
        )
        tool = self.config["tools"][0]
        await tool.handler(ToolInvocation(tool_call_id=str(number), tool_name="act", arguments={}))
        self.config["on_event"](
            event(
                "tool.execution_complete",
                tool_call_id=str(number),
                success=True,
                result={"content": "done"},
            )
        )
        return True

    async def dispatch_runtime_order(self, number: int) -> bool:
        self.config["on_event"](
            event("tool.execution_start", tool_call_id=str(number), tool_name="act", arguments={})
        )
        hook = self.config["hooks"]["on_pre_tool_use"]
        decision = await hook(
            {
                "sessionId": self.session_id,
                "timestamp": datetime.now(timezone.utc),
                "workingDirectory": ".",
                "toolName": "act",
                "toolArgs": {"number": number},
            },
            {},
        )
        if decision and decision.get("permissionDecision") == "deny":
            await asyncio.sleep(0)
            self.config["on_event"](
                event(
                    "tool.execution_complete",
                    tool_call_id=str(number),
                    success=False,
                    result={"content": "denied"},
                )
            )
            return False
        tool = self.config["tools"][0]
        await tool.handler(ToolInvocation(tool_call_id=str(number), tool_name="act", arguments={}))
        self.config["on_event"](
            event(
                "tool.execution_complete",
                tool_call_id=str(number),
                success=True,
                result={"content": "done"},
            )
        )
        return True


class FakeClient:
    def __init__(self, behavior: Any) -> None:
        self.behavior = behavior
        self.session: FakeSession | None = None
        self.stopped = False

    async def start(self) -> None:
        pass

    async def create_session(self, **config: Any) -> FakeSession:
        self.session = FakeSession(config, self.behavior)
        return self.session

    async def stop(self) -> None:
        self.stopped = True
        if self.session:
            self.session.config["on_event"](
                event("assistant.usage", model="actual-model", input_tokens=5, output_tokens=2)
            )

    async def force_stop(self) -> None:
        self.stopped = True


def fake_client(
    monkeypatch: pytest.MonkeyPatch, behavior: Any
) -> tuple[FakeClient, dict[str, Any]]:
    client = FakeClient(behavior)
    options: dict[str, Any] = {}

    def create(*args: Any, **kwargs: Any) -> FakeClient:
        options.update(kwargs)
        return client

    monkeypatch.setattr("pytest_skill_engineering.copilot.runner.create_client", create)
    return client, options


def test_controls_validate_and_do_not_leak_to_session() -> None:
    agent = CopilotEval(
        client_mode="empty", max_tool_calls=80, image_detail="high", audit_requests=True
    )
    config = agent.build_session_config()
    assert config["enable_config_discovery"] is False
    assert "max_tool_calls" not in config
    assert "image_detail" not in config
    invalid: list[dict[str, Any]] = [
        {"max_tool_calls": -1},
        {"max_tool_calls": True},
        {"image_detail": "tiny"},
    ]
    for kwargs in invalid:
        with pytest.raises(ValueError):
            CopilotEval(**kwargs)
    assert CopilotEval().client_mode == "copilot-cli"


async def test_empty_runtime_forwarding_and_no_inherited_persona(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("DO NOT INHERIT")

    async def behavior(session: FakeSession) -> None:
        assert "DO NOT INHERIT" not in str(session.config)

    client, options = fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(client_mode="empty", working_directory=str(tmp_path)), "go"
    )
    assert result.success
    assert options["mode"] == "empty"
    assert options["base_directory"]
    assert client.session is not None
    assert client.session.config["available_tools"] == []
    assert client.session.config["enable_file_hooks"] is False


async def test_budget_stops_instead_of_repeating_denials(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched: list[int] = []

    async def handler(invocation: ToolInvocation) -> ToolResult:
        dispatched.append(len(dispatched))
        return ToolResult(text_result_for_llm="done")

    async def behavior(session: FakeSession) -> None:
        assert await session.dispatch(1)
        assert await session.dispatch(2)
        assert not await session.dispatch(3)
        await asyncio.Event().wait()

    client, _ = fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(
            max_tool_calls=2,
            timeout_s=1,
            extra_config={"tools": [Tool("act", "act", handler)]},
        ),
        "go",
    )
    assert dispatched == [0, 1]
    assert not result.success
    assert result.stop_reason == "tool_budget_exceeded"
    assert result.tool_calls_admitted == 2
    assert client.session is not None and client.session.aborted
    assert client.stopped
    assert result.usage[-1].input_tokens == 5  # Cleanup events must not be lost.


async def test_budget_waits_for_last_admitted_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(invocation: ToolInvocation) -> ToolResult:
        entered.set()
        await release.wait()
        return ToolResult(text_result_for_llm="done")

    async def behavior(session: FakeSession) -> None:
        admitted = asyncio.create_task(session.dispatch(1))
        await entered.wait()
        assert not await session.dispatch(2)
        await asyncio.sleep(0)
        assert not session.aborted
        release.set()
        assert await admitted
        await asyncio.Event().wait()

    client, _ = fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(
            max_tool_calls=1,
            timeout_s=1,
            extra_config={"tools": [Tool("act", "act", handler)]},
        ),
        "go",
    )
    assert result.stop_reason == "tool_budget_exceeded"
    assert result.tool_calls_admitted == 1
    assert result.evidence_complete, result.capture_errors
    assert result.all_tool_calls[0].completion_received
    assert client.session is not None and client.session.aborted


async def test_budget_waits_for_denied_call_completion_in_runtime_event_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(invocation: ToolInvocation) -> ToolResult:
        return ToolResult(text_result_for_llm="done")

    async def behavior(session: FakeSession) -> None:
        assert await session.dispatch_runtime_order(1)
        assert not await session.dispatch_runtime_order(2)
        await asyncio.Event().wait()

    client, _ = fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(
            max_tool_calls=1,
            timeout_s=1,
            extra_config={"tools": [Tool("act", "act", handler)]},
        ),
        "go",
    )
    assert result.stop_reason == "tool_budget_exceeded"
    assert result.tool_calls_admitted == 1
    assert result.evidence_complete, result.capture_errors
    assert len(result.all_tool_calls) == 2
    assert all(call.completion_received for call in result.all_tool_calls)
    assert client.session is not None and client.session.aborted


async def test_caller_guard_survives_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    async def deny(data: Any, ctx: Any) -> PreToolUseHookOutput:
        return {"permissionDecision": "deny", "permissionDecisionReason": "owned window only"}

    async def behavior(session: FakeSession) -> None:
        assert not await session.dispatch(1)

    fake_client(monkeypatch, behavior)
    result = await run_copilot(CopilotEval(max_tool_calls=2, hooks={"on_pre_tool_use": deny}), "go")
    assert result.tool_calls_admitted == 0
    assert result.stop_reason == "completed"


async def test_timeout_drains_handler_and_preserves_incomplete_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finished = asyncio.Event()
    external: list[asyncio.Task[Any]] = []

    async def handler(invocation: ToolInvocation) -> ToolResult:
        await asyncio.sleep(0.08)
        finished.set()
        return ToolResult(text_result_for_llm="done")

    async def behavior(session: FakeSession) -> None:
        external.append(asyncio.create_task(session.dispatch(1)))
        await asyncio.Event().wait()

    client, _ = fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(
            timeout_s=0.02,
            extra_config={"tools": [Tool("act", "act", handler)]},
        ),
        "go",
    )
    assert finished.is_set()
    assert not result.success
    assert result.stop_reason == "timeout"
    assert client.stopped
    assert result.usage[-1].output_tokens == 2
    await asyncio.gather(*external)


async def test_startup_completion_cannot_swallow_execution_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def behavior(session: FakeSession) -> None:
        pass

    client, _ = fake_client(monkeypatch, behavior)
    create_session = client.create_session

    async def create_after_yield(**config: Any) -> FakeSession:
        await asyncio.sleep(0)
        return await create_session(**config)

    async def cancel_before_start_returns() -> None:
        execution = next(
            task
            for task in asyncio.all_tasks()
            if getattr(task.get_coro(), "__qualname__", "").endswith("run_copilot.<locals>.execute")
        )
        execution.cancel()

    monkeypatch.setattr(client, "start", cancel_before_start_returns)
    monkeypatch.setattr(client, "create_session", create_after_yield)
    with pytest.raises(asyncio.CancelledError):
        await run_copilot(CopilotEval(timeout_s=1), "go")
    assert client.stopped
    assert client.session is None


@pytest.mark.parametrize("shape", ["responses", "chat"])
async def test_audit_rewrites_actual_payload_and_headers(shape: str) -> None:
    from pytest_skill_engineering.copilot.requests import RequestAuditHandler

    observed: list[httpx.Request] = []

    async def send(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json={})

    payload: dict[str, Any] = {"model": "actual-model"}
    if shape == "responses":
        payload.update(
            instructions="actual system text",
            reasoning={"effort": "medium"},
            tools=[{"type": "function", "name": "act", "parameters": {}}],
            input=[{"role": "user", "content": [{"type": "input_image", "image_url": "secret"}]}],
        )
    else:
        payload.update(
            reasoning_effort="medium",
            tools=[{"type": "function", "function": {"name": "act"}}],
            messages=[
                {"role": "system", "content": "actual system text"},
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "secret"}}],
                },
            ],
        )
    handler = RequestAuditHandler(image_detail="high", audit=True)
    handler.http = httpx.AsyncClient(transport=httpx.MockTransport(send))
    try:
        await handler.send_request(
            httpx.Request("POST", context().url, json=payload, headers={"authorization": "secret"}),
            context(),
        )
    finally:
        await handler.aclose()
    request = observed[0]
    assert int(request.headers["content-length"]) == len(request.content)
    assert '"detail":"high"' in request.content.decode()
    record = serialize_dataclass(handler.records[0])
    assert record["model"] == "actual-model"
    assert record["tool_names"] == ["act"]
    assert record["reasoning_effort"] == "medium"
    assert record["image_details"] == ["high"]
    assert record["image_count"] == 1
    assert record["instructions_sha256"] == hashlib.sha256(b"actual system text").hexdigest()
    assert "secret" not in json.dumps(record)
    assert "actual system text" not in json.dumps(record)


async def test_invalid_request_is_not_forwarded() -> None:
    from pytest_skill_engineering.copilot.requests import RequestAuditHandler

    handler = RequestAuditHandler(image_detail="high", audit=True)
    with pytest.raises(ValueError, match="Unsupported"):
        await handler.send_request(
            httpx.Request("POST", context().url, json={"model": "x", "unknown": []}), context()
        )
    assert handler.failed.is_set()
    assert handler.records == []
    await handler.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "", "input": []},
        {"model": "x", "messages": [], "system": "unsupported provider instructions"},
        {"model": "x", "input": [], "tools": [{"type": "function", "name": ""}]},
        {"model": "x", "input": [{"role": "user", "content": [{"type": "input_image"}]}]},
        {
            "model": "x",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"detail": "high"}}],
                }
            ],
        },
    ],
)
async def test_malformed_audit_cannot_be_counted_as_valid(payload: dict[str, Any]) -> None:
    from pytest_skill_engineering.copilot.requests import RequestAuditHandler

    handler = RequestAuditHandler(image_detail="high", audit=True)
    with pytest.raises(ValueError, match="Unsupported"):
        await handler.send_request(httpx.Request("POST", context().url, json=payload), context())
    assert handler.observed_requests == 0
    assert handler.failed.is_set()


async def test_missing_audit_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def behavior(session: FakeSession) -> None:
        pass

    fake_client(monkeypatch, behavior)
    result = await run_copilot(CopilotEval(audit_requests=True), "go")
    assert not result.success
    assert result.stop_reason == "request_audit_error"
    assert not result.evidence_complete


def test_usage_nullable_counts_and_native_serialization() -> None:
    mapper = EventMapper()
    mapper.handle(
        event(
            "assistant.usage",
            model="actual-model",
            input_tokens=12,
            output_tokens=7,
            reasoning_tokens=3,
            cache_read_tokens=None,
            cache_write_tokens=2,
            reasoning_effort="medium",
            duration=timedelta(seconds=0.5),
        )
    )
    result = mapper.build()
    usage = result.usage[0]
    assert usage.cache_read_tokens is None
    assert usage.cache_write_tokens == 2
    assert usage.reasoning_tokens == 3
    assert usage.reasoning_effort == "medium"
    assert usage.duration_ms == 500
    converted = _convert_to_aitest(CopilotEval(), result)
    assert converted is not None
    data = serialize_dataclass(converted[0])
    assert data["usage"][0]["cache_read_tokens"] is None
    assert data["usage"][0]["reasoning_tokens"] == 3
    assert "request_audit" in data
    assert "stop_reason" in data
    json.dumps(data)


async def test_parallel_admissions_never_exceed_cap() -> None:
    from pytest_skill_engineering.copilot.controls import RunControls

    controls = RunControls(80)
    config: dict[str, Any] = {}
    controls.install(config, {})
    before = config["hooks"]["on_pre_tool_use"]
    outcomes = await asyncio.gather(*(before({}, {}) for _ in range(100)))
    assert (
        sum(not output or output.get("permissionDecision") != "deny" for output in outcomes) == 80
    )
    assert controls.admitted == 80
    assert not controls.budget_exceeded.is_set()
    for index in range(81):
        controls.observe(event("tool.execution_start", tool_call_id=str(index)))
    for index in range(80):
        controls.observe(event("tool.execution_complete", tool_call_id=str(index)))
    assert not controls.budget_exceeded.is_set()
    controls.observe(event("tool.execution_complete", tool_call_id="80"))
    assert controls.budget_exceeded.is_set()


async def test_admitted_handler_starts_after_budget_closes_dispatch() -> None:
    from pytest_skill_engineering.copilot.controls import RunControls

    invoked = False

    async def handler(invocation: ToolInvocation) -> ToolResult:
        nonlocal invoked
        invoked = True
        return ToolResult(text_result_for_llm="done")

    controls = RunControls(1)
    config: dict[str, Any] = {"tools": [Tool("act", "act", handler)]}
    controls.install(config, {})
    before = config["hooks"]["on_pre_tool_use"]
    assert await before({}, {}) is None
    denied = await before({}, {})
    assert denied["permissionDecision"] == "deny"

    wrapped = config["tools"][0]
    assert wrapped.handler is not None
    await wrapped.handler(ToolInvocation(tool_call_id="admitted", tool_name="act", arguments={}))
    assert invoked


async def test_persona_and_user_guards_compose_without_mutation() -> None:
    from pytest_skill_engineering.copilot.controls import RunControls

    calls: list[str] = []

    async def caller(data: Any, context: Any) -> PreToolUseHookOutput:
        calls.append("caller")
        return {
            "permissionDecision": "ask",
            "modifiedArgs": {"safe": True},
            "additionalContext": "caller",
        }

    def persona(data: Any, context: Any) -> PreToolUseHookOutput:
        calls.append("persona")
        assert data["toolArgs"] == {"safe": True}
        return {"permissionDecision": "allow", "additionalContext": "persona"}

    original = {"on_pre_tool_use": caller}
    config: dict[str, Any] = {"hooks": {"on_pre_tool_use": persona}}
    controls = RunControls(2)
    controls.install(config, original)
    output = await config["hooks"]["on_pre_tool_use"]({"toolArgs": {}}, {})
    assert output["permissionDecision"] == "ask"
    assert output["additionalContext"] == "caller\npersona"
    assert calls == ["caller", "persona"]
    assert original["on_pre_tool_use"] is caller


async def test_guard_exception_denies_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    def guard(data: Any, ctx: Any) -> PreToolUseHookOutput:
        raise RuntimeError("guard failed")

    async def behavior(session: FakeSession) -> None:
        assert not await session.dispatch(1)
        await asyncio.Event().wait()

    fake_client(monkeypatch, behavior)
    result = await run_copilot(CopilotEval(hooks={"on_pre_tool_use": guard}), "go")
    assert not result.success
    assert result.stop_reason == "execution_error"
    assert result.tool_calls_admitted == 0
    assert "guard failed" in (result.error or "")


async def test_cancellation_of_sdk_callback_does_not_release_live_action() -> None:
    from pytest_skill_engineering.copilot.controls import RunControls

    entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def handler(invocation: ToolInvocation) -> ToolResult:
        entered.set()
        await release.wait()
        finished.set()
        return ToolResult()

    controls = RunControls(None)
    tool = controls.wrap(Tool("act", "act", handler))
    assert tool.handler is not None
    pending = tool.handler(ToolInvocation())
    assert inspect.isawaitable(pending)
    task = asyncio.ensure_future(pending)
    await entered.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    draining = asyncio.create_task(controls.drain())
    await asyncio.sleep(0)
    assert not draining.done()
    assert not finished.is_set()
    release.set()
    assert await draining == []
    assert finished.is_set()
    assert not controls.active


async def test_timeout_keeps_missing_completion_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    async def behavior(session: FakeSession) -> None:
        session.config["on_event"](
            event("tool.execution_start", tool_call_id="lost", tool_name="act", arguments={})
        )
        await asyncio.Event().wait()

    fake_client(monkeypatch, behavior)
    result = await run_copilot(CopilotEval(timeout_s=0.02), "go")
    assert result.stop_reason == "timeout"
    assert not result.evidence_complete
    assert result.all_tool_calls[0].completion_received is False
    converted = _convert_to_aitest(CopilotEval(), result)
    assert converted is not None
    data = serialize_dataclass(converted[0])
    assert data["stop_reason"] == "timeout"
    assert data["evidence_complete"] is False
    assert "missing completion" in data["capture_errors"][0]
    assert (
        data["capture_errors"][1]
        == "Tool lifecycle incomplete: call=lost, start_ordinal=1, admitted=0, "
        "handler=not_started, sdk_completion=missing, abort_phase=timeout"
    )
    assert data["usage"][-1]["input_tokens"] == 5


async def test_single_attempt_after_uncertain_action(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    async def handler(invocation: ToolInvocation) -> ToolResult:
        return ToolResult()

    async def behavior(session: FakeSession) -> None:
        nonlocal attempts
        attempts += 1
        await session.dispatch(1)
        raise RuntimeError("fetch failed")

    fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(extra_config={"tools": [Tool("act", "act", handler)]}), "go"
    )
    assert not result.success
    assert attempts == 1


async def test_cleanup_failure_cannot_look_successful(monkeypatch: pytest.MonkeyPatch) -> None:
    async def behavior(session: FakeSession) -> None:
        pass

    client, _ = fake_client(monkeypatch, behavior)

    async def fail() -> None:
        raise RuntimeError("stop failed")

    monkeypatch.setattr(client, "stop", fail)
    result = await run_copilot(CopilotEval(), "go")
    assert result.stop_reason == "cleanup_error"
    assert not result.success
    assert not result.evidence_complete
    assert client.stopped  # Forced cleanup still attempted.


async def test_audit_records_in_native_json_with_bound_handler(tmp_path: Any) -> None:
    from pytest_skill_engineering.copilot.requests import RequestAudit
    from pytest_skill_engineering.copilot.result import CopilotResult, UsageInfo
    from pytest_skill_engineering.core.serialization import deserialize_suite_report
    from pytest_skill_engineering.reporting.collector import TestReport, build_suite_report
    from pytest_skill_engineering.reporting.generator import generate_json

    class Adapter:
        async def act(self, invocation: ToolInvocation) -> ToolResult:
            raise AssertionError("Must never execute")

    agent = CopilotEval(
        name="fixture",
        extra_config={
            "tools": [
                Tool(
                    "act",
                    "owned window",
                    Adapter().act,
                    parameters={"type": "object", "properties": {}},
                    metadata={"route": "controls"},
                )
            ]
        },
    )
    result = CopilotResult(
        success=False,
        error="budget",
        stop_reason="tool_budget_exceeded",
        request_audit=[RequestAudit("r1", "actual", ["act"], "medium", ["high"], 1, "abc")],
        usage=[UsageInfo(model="actual", input_tokens=3, output_tokens=4, reasoning_tokens=2)],
        tool_calls_admitted=80,
    )
    converted = _convert_to_aitest(agent, result)
    assert converted is not None
    report = build_suite_report(
        [
            TestReport(
                name="test_trial",
                outcome="failed",
                duration_ms=10,
                eval_result=converted[0],
                properties=[("build_hash", "immutable")],
            )
        ],
        "benchmark",
    )
    path = tmp_path / "native.json"
    generate_json(report, path)
    data = json.loads(path.read_text())
    row = data["tests"][0]
    assert row["properties"] == [["build_hash", "immutable"]]
    assert row["eval_result"]["request_audit"][0]["image_count"] == 1
    assert row["eval_result"]["configuration"]["tools"][0]["metadata"] == {"route": "controls"}
    assert "handler" not in row["eval_result"]["configuration"]["tools"][0]
    assert row["eval_result"]["usage"][0]["cache_write_tokens"] is None
    restored = deserialize_suite_report(data)
    assert restored.tests[0].eval_result == converted[0]


async def test_streamed_request_rebuilds_length_and_developer_hash() -> None:
    from pytest_skill_engineering.copilot.requests import RequestAuditHandler

    async def stream() -> AsyncIterator[bytes]:
        yield json.dumps(
            {
                "model": "actual",
                "instructions": "system",
                "input": [
                    {"role": "developer", "content": [{"type": "input_text", "text": "developer"}]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": "secret", "detail": "low"},
                            {"type": "input_image", "image_url": "secret2", "detail": "auto"},
                        ],
                    },
                ],
            }
        ).encode()

    async def send(request: httpx.Request) -> httpx.Response:
        assert "transfer-encoding" not in request.headers
        assert int(request.headers["content-length"]) == len(request.content)
        assert request.content.count(b'"detail":"high"') == 2
        return httpx.Response(200)

    handler = RequestAuditHandler(image_detail="high", audit=True)
    handler.http = httpx.AsyncClient(transport=httpx.MockTransport(send))
    await handler.send_request(httpx.Request("POST", context().url, content=stream()), context())
    assert (
        handler.records[0].instructions_sha256 == hashlib.sha256(b"system\n\ndeveloper").hexdigest()
    )
    assert handler.records[0].image_count == 2
    await handler.aclose()


def test_missing_usage_is_not_claimed_zero() -> None:
    mapper = EventMapper()
    mapper.handle(event("assistant.usage", model="actual"))
    result = mapper.build()
    assert result.usage[0].reasoning_tokens is None
    assert result.total_tokens is None
    assert result.token_usage == {}
    mapper.handle(event("assistant.usage", model="actual", input_tokens=1, output_tokens=2))
    assert mapper.build().total_tokens is None


async def test_controls_forwarding_keeps_permission_and_event_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from copilot.generated.rpc import PermissionDecisionReject

    events: list[Any] = []

    def permission(*args: Any, **kwargs: Any) -> PermissionDecisionReject:
        return PermissionDecisionReject()

    async def behavior(session: FakeSession) -> None:
        assert session.config["on_permission_request"] is permission
        assert session.config["reasoning_effort"] == "medium"
        assert session.config["model"] == "gpt-6-luna"
        assert session.config["available_tools"] == ["act"]
        assert session.config["system_message"]["content"] == "system"
        for field in ("client_mode", "max_tool_calls", "image_detail", "audit_requests"):
            assert field not in session.config

    fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(
            client_mode="empty",
            model="gpt-6-luna",
            reasoning_effort="medium",
            instructions="system",
            timeout_s=600,
            max_tool_calls=80,
            allowed_tools=["act"],
            extra_config={"on_permission_request": permission, "on_event": events.append},
        ),
        "go",
    )
    assert result.success
    assert len(events) == 1


async def test_request_audit_failure_wakes_runner_before_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: dict[str, Any]

    async def behavior(session: FakeSession) -> None:
        handler = options["request_handler"]
        with pytest.raises(ValueError, match="Unsupported"):
            await handler.send_request(
                httpx.Request("POST", context().url, json={"unexpected": "secret"}), context()
            )
        await asyncio.Event().wait()

    client, options = fake_client(monkeypatch, behavior)
    result = await run_copilot(CopilotEval(audit_requests=True, timeout_s=600), "go")
    assert result.stop_reason == "request_audit_error"
    assert not result.evidence_complete
    assert client.session is not None and client.session.aborted
    assert "secret" not in (result.error or "")


def test_sdk_usage_fields_are_preserved() -> None:
    from copilot.generated.session_events import AssistantUsageData, SessionEvent, SessionEventType

    data = AssistantUsageData.from_dict(
        {
            "model": "gpt-6-luna",
            "inputTokens": 10,
            "outputTokens": 20,
            "cacheReadTokens": 0,
            "cacheWriteTokens": 4,
            "reasoningTokens": 5,
            "reasoningEffort": "medium",
            "duration": 100,
        }
    )
    mapper = EventMapper()
    mapper.handle(
        SessionEvent(
            type=SessionEventType("assistant.usage"),
            data=data,
            id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
    )
    usage = mapper.build().usage[0]
    assert usage.input_tokens == 10
    assert usage.cache_read_tokens == 0
    assert usage.cache_write_tokens == 4
    assert usage.reasoning_tokens == 5
    assert usage.reasoning_effort == "medium"
    assert usage.duration_ms == 100


@pytest.mark.parametrize(
    "settings",
    [
        {"audit_requests": True},
        {"image_detail": "high"},
        {"audit_requests": True, "image_detail": "high"},
    ],
)
@pytest.mark.parametrize("websockets", [True, False, None])
async def test_audited_execution_preserves_transport_options(
    monkeypatch: pytest.MonkeyPatch,
    settings: dict[str, Any],
    websockets: bool | None,
) -> None:
    options: dict[str, Any]
    supplied_capi: dict[str, Any] = {"auto_tier": "intelligence"}
    if websockets is not None:
        supplied_capi["enable_web_socket_responses"] = websockets
    observed: list[httpx.Request] = []

    async def send(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200)

    async def behavior(session: FakeSession) -> None:
        handler = options["request_handler"]
        assert session.config["capi"] == supplied_capi
        handler.http = httpx.AsyncClient(transport=httpx.MockTransport(send))
        await handler.send_request(
            httpx.Request(
                "POST",
                context().url,
                json={
                    "model": "actual-model",
                    "instructions": "actual instructions",
                    "reasoning": {"effort": "medium"},
                    "tools": [{"type": "function", "name": "act"}],
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_image", "image_url": "secret", "detail": "low"},
                            ],
                        }
                    ],
                },
            ),
            context(),
        )

    client, options = fake_client(monkeypatch, behavior)
    result = await run_copilot(CopilotEval(**settings, extra_config={"capi": supplied_capi}), "go")
    assert result.success, result.error
    assert result.stop_reason == "completed"
    assert result.evidence_complete
    assert len(observed) == 1
    assert supplied_capi.get("enable_web_socket_responses") is websockets
    if settings.get("audit_requests"):
        assert result.request_audit[0].model == "actual-model"
        assert result.request_audit[0].tool_names == ["act"]
        assert result.request_audit[0].reasoning_effort == "medium"
        assert result.request_audit[0].image_count == 1
        assert (
            result.request_audit[0].instructions_sha256
            == hashlib.sha256(b"actual instructions").hexdigest()
        )
    if settings.get("image_detail"):
        assert b'"detail":"high"' in observed[0].content


@pytest.mark.parametrize("capi", [None, {"enable_web_socket_responses": True}])
async def test_ordinary_execution_keeps_sdk_transport_default(
    monkeypatch: pytest.MonkeyPatch,
    capi: Any,
) -> None:
    async def behavior(session: FakeSession) -> None:
        assert session.config.get("capi") == capi

    fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(extra_config={"capi": capi} if capi is not None else {}), "go"
    )
    assert result.success


async def test_actual_sdk_serializes_caller_http_preference_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from copilot import CopilotClient

    class WireCaptured(Exception):
        pass

    class OfflineConnection:
        async def request(self, method: str, payload: dict[str, Any], **kwargs: Any) -> None:
            assert method == "session.create"
            assert payload["capi"] == {
                "autoTier": "intelligence",
                "enableWebSocketResponses": False,
            }
            raise WireCaptured

    async def forbidden_start(self: Any) -> None:
        pytest.fail("Offline SDK test must not start a real runtime")

    monkeypatch.setattr(CopilotClient, "start", forbidden_start)

    async def behavior(session: FakeSession) -> None:
        client = CopilotClient()
        monkeypatch.setattr(client, "_client", OfflineConnection())
        with pytest.raises(WireCaptured):
            await client.create_session(**session.config)

    fake_client(monkeypatch, behavior)
    result = await run_copilot(
        CopilotEval(
            image_detail="high",
            extra_config={
                "capi": {"auto_tier": "intelligence", "enable_web_socket_responses": False}
            },
        ),
        "go",
    )
    # The fake SDK boundary intentionally emits no inference request.
    assert result.stop_reason == "request_audit_error", result.error
    assert "No outbound model requests captured" in (result.error or "")
