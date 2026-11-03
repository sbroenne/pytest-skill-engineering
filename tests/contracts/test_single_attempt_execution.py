"""Offline attempt/evidence contracts, not model-performance tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from pytest_copilot.copilot import CopilotTask, runner
from pytest_copilot.copilot.fixtures import _convert_to_aitest
from pytest_copilot.reporting import build_suite_report, generate_json, load_suite_report
from pytest_copilot.reporting.collector import TestReport as CaseReport


class StructuredAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    count: int


@pytest.mark.parametrize("phase", ["start", "create", "execute"])
@pytest.mark.parametrize("message", ["fetch failed", "ECONNRESET", "SDK TimeoutError"])
async def test_failure_is_one_attempt_with_cleanup_and_original_evidence(
    monkeypatch: pytest.MonkeyPatch, phase: str, message: str
) -> None:
    counts = {"created": 0, "start": 0, "create": 0, "execute": 0, "stop": 0, "abort": 0}
    config: dict[str, Any] = {}

    class Session:
        session_id = "offline-session"

        async def send_and_wait(self, prompt: str, timeout: float) -> None:
            counts["execute"] += 1
            config["on_event"](
                SimpleNamespace(
                    type="assistant.usage",
                    data=SimpleNamespace(model="offline", input_tokens=7, output_tokens=3),
                )
            )
            raise RuntimeError(message)

        async def abort(self) -> None:
            counts["abort"] += 1

    class Client:
        async def start(self) -> None:
            counts["start"] += 1
            if phase == "start":
                raise RuntimeError(message)

        async def create_session(self, **settings: Any) -> Session:
            counts["create"] += 1
            config.update(settings)
            if phase == "create":
                raise RuntimeError(message)
            return Session()

        async def stop(self) -> None:
            counts["stop"] += 1

    def create_client(*args: Any, **kwargs: Any) -> Client:
        counts["created"] += 1
        return Client()

    monkeypatch.setattr(runner, "create_client", create_client)
    agent = CopilotTask(model="offline", client_mode="empty")
    result = await runner.run_copilot(agent, "Check one attempt.")
    assert counts["created"] == counts["start"] == counts["stop"] == 1
    assert counts["create"] == (0 if phase == "start" else 1)
    assert counts["execute"] == counts["abort"] == (1 if phase == "execute" else 0)
    assert result.agent is agent
    assert not result.success and result.stop_reason == "execution_error"
    assert result.error == message
    if phase == "execute":
        assert result.usage[0].input_tokens == 7
        assert result.usage[0].output_tokens == 3
    converted = _convert_to_aitest(agent, result)
    assert converted is not None
    saved, _ = converted
    assert not {"max_retries", "retry_delay_s"} & saved.configuration.keys()


@pytest.mark.parametrize("setting", ["max_retries", "retry_delay_s"])
def test_retry_settings_are_not_accepted(setting: str) -> None:
    kwargs: dict[str, Any] = {setting: 0}
    with pytest.raises(TypeError, match=setting):
        CopilotTask(**kwargs)


@pytest.mark.parametrize(
    ("content", "valid"),
    [
        ('{"count": 42}', True),
        ('{"count": "invalid"}', False),
        ('{"count": 42, "extra": true}', False),
        ("not JSON", False),
        ("", False),
    ],
)
async def test_structured_response_preserves_execution_and_saved_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str, valid: bool
) -> None:
    config: dict[str, Any] = {}
    counts = {"typed_send": 0, "stop": 0, "abort": 0}

    class Session:
        async def send_and_wait_typed(
            self, prompt: str, response_type: type[BaseModel], timeout: float
        ) -> BaseModel:
            counts["typed_send"] += 1
            assert response_type is StructuredAnswer
            config["on_event"](
                SimpleNamespace(type="assistant.message", data=SimpleNamespace(content=content))
            )
            return response_type.model_validate_json(content)

        async def abort(self) -> None:
            counts["abort"] += 1

    class Client:
        async def start(self) -> None:
            pass

        async def create_session(self, **settings: Any) -> Session:
            assert "response_schema" not in settings
            config.update(settings)
            return Session()

        async def stop(self) -> None:
            counts["stop"] += 1

    monkeypatch.setattr(runner, "create_client", lambda *args, **kwargs: Client())
    agent = CopilotTask(client_mode="empty", response_schema=StructuredAnswer)
    result = await runner.run_copilot(agent, "Return the count.")
    assert counts == {"typed_send": 1, "stop": 1, "abort": 0 if valid else 1}
    assert result.success is valid
    assert result.final_response == (content if content else None)
    assert result.raw_events[0].data.content == content
    assert result.configuration is not None
    assert result.configuration["response_schema"] == StructuredAnswer.model_json_schema()
    if valid:
        assert json.loads(content)["count"] == 42
    else:
        assert result.stop_reason == "execution_error"
        assert result.error
    converted = _convert_to_aitest(agent, result)
    assert converted is not None
    suite = build_suite_report(
        [CaseReport("structured", "passed" if valid else "failed", 1, converted[0])],
        "Structured evidence",
    )
    output = tmp_path / "structured.json"
    generate_json(suite, output)
    saved = load_suite_report(output).tests[0].eval_result
    assert saved is not None
    assert saved.success is valid
    assert saved.error == result.error
    assert saved.configuration is not None
    assert saved.configuration["response_schema"] == StructuredAnswer.model_json_schema()
    assert [turn.content for turn in saved.turns] == ([content] if content else [])


@pytest.mark.parametrize("schema", [{}, str, StructuredAnswer(count=42)])
def test_response_schema_requires_a_pydantic_model_class(schema: Any) -> None:
    with pytest.raises(TypeError, match="response_schema must be a Pydantic model class"):
        CopilotTask(response_schema=schema)


def test_response_schema_applies_only_to_the_parent_answer() -> None:
    parent = CopilotTask(response_schema=StructuredAnswer)
    child = parent.create_subagent(
        name="child",
        model=None,
        reasoning_effort=None,
        instructions="Look up the count.",
        timeout_s=30,
        max_turns=5,
        allowed_tools=None,
        mcp_servers={},
    )
    assert parent.response_schema is StructuredAnswer
    assert child.response_schema is None
