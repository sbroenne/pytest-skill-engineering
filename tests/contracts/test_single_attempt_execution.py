"""Offline attempt/evidence contracts, not model-performance tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pytest_skill_engineering.copilot import CopilotEval, runner
from pytest_skill_engineering.copilot.fixtures import _convert_to_aitest


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
    agent = CopilotEval(model="offline", client_mode="empty")
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
        CopilotEval(**kwargs)
