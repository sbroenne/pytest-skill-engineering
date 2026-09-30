"""Model-free checks against a real loopback WebSocket connection."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from copilot import CopilotRequestContext
from websockets.asyncio.server import ServerConnection, serve

from pytest_skill_engineering.copilot.requests import RequestAuditHandler
from pytest_skill_engineering.core.serialization import serialize_dataclass


@dataclass(slots=True)
class ResponseBridge:
    messages: asyncio.Queue[str | bytes] = field(default_factory=asyncio.Queue)

    async def write(self, data: str | bytes) -> None:
        self.messages.put_nowait(data)

    async def end(self) -> None:
        pass

    async def error(self, *args: Any) -> None:
        pass


def websocket_context(url: str, bridge: Any) -> CopilotRequestContext:
    return CopilotRequestContext(
        request_id="connection-1",
        transport="websocket",
        url=url,
        headers={"authorization": ["secret-token"]},
        cancel_event=asyncio.Event(),
        _bridge=bridge,
    )


def request_payload() -> dict[str, Any]:
    return {
        "type": "response.create",
        "model": "actual-model",
        "instructions": "actual instructions",
        "tools": [{"type": "function", "name": "act", "parameters": {}}],
        "reasoning": {"effort": "medium"},
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_image", "image_url": "secret-image", "detail": "low"}],
            }
        ],
    }


@pytest.mark.parametrize("audit", [True, False])
async def test_repeated_websocket_requests_are_rewritten_before_forwarding(audit: bool) -> None:
    observed: list[dict[str, Any]] = []
    disconnected = asyncio.Event()

    async def upstream(socket: ServerConnection) -> None:
        try:
            async for message in socket:
                observed.append(json.loads(message))
                await socket.send('{"type":"response.completed"}')
        finally:
            disconnected.set()

    async with serve(upstream, "127.0.0.1", 0) as server:
        bridge = ResponseBridge()
        ctx = websocket_context(f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}", bridge)
        owner = RequestAuditHandler(image_detail="high", audit=audit)
        try:
            socket = await owner.open_websocket(ctx)
            await socket.open()
            for index in range(3):
                payload = request_payload()
                if index:
                    payload["previous_response_id"] = "previous-response"
                    payload["model"] = "second-model"
                    payload["tools"] = [{"type": "function", "name": "second-tool"}]
                    payload["instructions"] = "second instructions"
                if index == 2:
                    payload["input"] = []
                    payload["instructions"] = ""
                    payload["tools"] = []
                    del payload["reasoning"]
                await socket.send_request_message(json.dumps(payload))
                assert await asyncio.wait_for(bridge.messages.get(), 2) == (
                    '{"type":"response.completed"}'
                )
            assert len(observed) == 3
            assert all(p["input"][0]["content"][0]["detail"] == "high" for p in observed[:2])
            assert observed[1]["previous_response_id"] == "previous-response"
            assert owner.observed_requests == 3
            if audit:
                first, second, third = owner.records
                assert first.request_id == second.request_id == "connection-1"
                assert first.model == "actual-model"
                assert second.model == "second-model"
                assert first.tool_names == ["act"]
                assert second.tool_names == ["second-tool"]
                assert (
                    second.instructions_sha256 == hashlib.sha256(b"second instructions").hexdigest()
                )
                assert first.reasoning_effort == "medium"
                assert first.image_count == 1
                assert first.image_details == ["high"]
                assert third.reasoning_effort is None
                assert third.tool_names == []
                assert third.image_count == 0
                assert third.instructions_sha256 == hashlib.sha256(b"").hexdigest()
                evidence = json.dumps(serialize_dataclass(first))
                assert "secret" not in evidence and "actual instructions" not in evidence
            else:
                assert owner.records == []
        finally:
            await owner.aclose()
        await asyncio.wait_for(disconnected.wait(), 2)


@pytest.mark.parametrize(
    "frame",
    [
        "secret-invalid-json",
        b'{"type":"response.create"}',
        '{"type":"response.cancel"}',
        '{"type":"response.create","response":{"model":"x","input":[]}}',
        *[
            json.dumps(
                {
                    k: v
                    for k, v in {**request_payload(), "previous_response_id": "r1"}.items()
                    if k != missing
                }
            )
            for missing in ("model", "instructions", "tools", "input")
        ],
    ],
)
async def test_unsupported_websocket_frames_never_reach_upstream(frame: str | bytes) -> None:
    observed: list[str | bytes] = []

    async def upstream(socket: ServerConnection) -> None:
        async for message in socket:
            observed.append(message)

    async with serve(upstream, "127.0.0.1", 0) as server:
        owner = RequestAuditHandler(image_detail="high", audit=True)
        ctx = websocket_context(
            f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}", ResponseBridge()
        )
        try:
            socket = await owner.open_websocket(ctx)
            await socket.open()
            with pytest.raises(ValueError, match="Unsupported"):
                await socket.send_request_message(frame)
            assert owner.failed.is_set()
            assert "secret" not in (owner.error or "")
            assert owner.records == [] and owner.observed_requests == 0
            with pytest.raises(ValueError, match="already failed"):
                await socket.send_request_message(json.dumps(request_payload()))
            with pytest.raises(ValueError, match="already failed"):
                await owner.send_request(
                    httpx.Request(
                        "POST", "https://example.invalid/responses", json=request_payload()
                    ),
                    ctx,
                )
        finally:
            await owner.aclose()
        assert observed == []


async def test_websocket_transport_failure_blocks_http_fallback() -> None:
    async def upstream(socket: ServerConnection) -> None:
        await socket.recv()
        await socket.close(1011, "secret-error")

    async with serve(upstream, "127.0.0.1", 0) as server:
        owner = RequestAuditHandler(image_detail="high", audit=True)
        ctx = websocket_context(
            f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}", ResponseBridge()
        )
        try:
            socket = await owner.open_websocket(ctx)
            await socket.open()
            await socket.send_request_message(json.dumps(request_payload()))
            await asyncio.wait_for(owner.failed.wait(), 2)
            assert "secret" not in (owner.error or "")
            with pytest.raises(ValueError, match="already failed"):
                await owner.send_request(
                    httpx.Request(
                        "POST", "https://example.invalid/responses", json=request_payload()
                    ),
                    ctx,
                )
        finally:
            await owner.aclose()


async def test_websocket_cannot_silently_drop_message_before_open() -> None:
    owner = RequestAuditHandler(image_detail="high", audit=True)
    socket = await owner.open_websocket(websocket_context("ws://example.invalid", ResponseBridge()))
    try:
        with pytest.raises(ValueError, match="not open"):
            await socket.send_request_message(json.dumps(request_payload()))
        assert owner.failed.is_set()
        assert owner.observed_requests == 0 and owner.records == []
    finally:
        await owner.aclose()


async def test_websocket_open_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(*args: Any, **kwargs: Any) -> None:
        raise OSError("secret endpoint and authorization")

    monkeypatch.setattr("websockets.connect", unavailable)
    owner = RequestAuditHandler(image_detail="high", audit=True)
    socket = await owner.open_websocket(websocket_context("ws://example.invalid", ResponseBridge()))
    try:
        with pytest.raises(ValueError, match="transport open failed: OSError"):
            await socket.open()
        assert owner.failed.is_set()
        assert "secret" not in (owner.error or "")
    finally:
        await owner.aclose()


async def test_transport_cleanup_attempts_every_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = RequestAuditHandler(image_detail="high", audit=True)
    first = await owner.open_websocket(websocket_context("ws://example.invalid", ResponseBridge()))
    second = await owner.open_websocket(websocket_context("ws://example.invalid", ResponseBridge()))
    finished = asyncio.Event()

    async def broken_close() -> None:
        raise OSError("synthetic cleanup failure")

    async def slow_close() -> None:
        await asyncio.sleep(0.01)
        finished.set()

    monkeypatch.setattr(first, "aclose", broken_close)
    monkeypatch.setattr(second, "aclose", slow_close)
    with pytest.raises(ExceptionGroup, match="transport cleanup failed"):
        await owner.aclose()
    assert finished.is_set()
