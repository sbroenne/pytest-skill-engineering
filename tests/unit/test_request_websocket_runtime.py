"""Offline native-runtime regression; requires PYTEST_COPILOT_RUNTIME_PATH.

The supplied cached runtime talks only to dummy authentication and a loopback
Responses server. No model, real credentials, or desktop tools are used.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from copilot import CopilotClient, StdioRuntimeConnection
from copilot.session import ModelCapabilitiesOverride, ModelSupportsOverride
from copilot.tools import Tool, ToolBinaryResult, ToolInvocation, ToolResult
from websockets.asyncio.server import ServerConnection, serve

from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.copilot.fixtures import _convert_to_aitest
from pytest_skill_engineering.core.serialization import serialize_dataclass

PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/"
    "AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg=="
)


class LocalOnlyAPI(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == "/copilot_internal/user":
            body = json.dumps({"login": "offline", "id": 1}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Offline test endpoint")

    def do_CONNECT(self) -> None:
        self.send_error(503, "No external connections in offline test")

    def do_POST(self) -> None:
        self.send_error(503, "No inference or proxy forwarding in offline test")


async def respond(socket: ServerConnection, index: int, *, request_tool: bool = False) -> None:
    response_id = f"response-{index}"
    if index == 1 or request_tool:
        item = {
            "id": f"tool-{index}",
            "type": "function_call",
            "call_id": f"call-{index}",
            "name": "memory_image",
            "arguments": "{}",
            "status": "completed",
        }
    else:
        item = {
            "id": "message-1",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Ready.", "annotations": []}],
        }
    response = {
        "id": response_id,
        "object": "response",
        "model": "offline-model",
        "status": "in_progress",
        "output": [],
    }
    events: list[dict[str, Any]] = [
        {"type": "response.created", "response": response},
        {"type": "response.output_item.added", "output_index": 0, "item": item},
    ]
    if item["type"] == "message":
        events.append(
            {
                "type": "response.output_text.delta",
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "delta": "Ready.",
            }
        )
    events.extend(
        [
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {
                "type": "response.completed",
                "response": {
                    **response,
                    "status": "completed",
                    "output": [item],
                    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                },
            },
        ]
    )
    for sequence, event in enumerate(events):
        await socket.send(json.dumps({**event, "sequence_number": sequence}))


@pytest.mark.parametrize(
    "outcome", ["completed", "disconnected", "timeout", "tool_budget_exceeded"]
)
async def test_native_runtime_websocket_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, copilot_eval: Any, outcome: str
) -> None:
    runtime = os.environ.get("PYTEST_COPILOT_RUNTIME_PATH")
    if not runtime:
        pytest.skip("Set PYTEST_COPILOT_RUNTIME_PATH to an already cached native runtime")
    assert Path(runtime).is_file(), "Offline runtime path must exist; never download in this test"

    api = ThreadingHTTPServer(("127.0.0.1", 0), LocalOnlyAPI)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    api_url = f"http://127.0.0.1:{api.server_port}"
    env = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "PATHEXT")
        if key in os.environ
    }
    env.update(
        {
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path),
            "LOCALAPPDATA": str(tmp_path),
            "COPILOT_API_URL": api_url,
            "COPILOT_DEBUG_GITHUB_API_URL": api_url,
            "GITHUB_COPILOT_API_TOKEN": "offline-api-token",
            "HTTP_PROXY": api_url,
            "HTTPS_PROXY": api_url,
            "ALL_PROXY": api_url,
            "NO_PROXY": "127.0.0.1,localhost",
        }
    )

    def create(working_directory: str, **kwargs: Any) -> CopilotClient:
        return CopilotClient(
            working_directory=working_directory,
            connection=StdioRuntimeConnection(path=runtime),
            env=env,
            github_token="offline-github-token",
            use_logged_in_user=False,
            **kwargs,
        )

    monkeypatch.setattr("pytest_skill_engineering.copilot.runner.create_client", create)
    frames: list[dict[str, Any]] = []
    connections: list[ServerConnection] = []
    tools_called: list[str] = []

    async def upstream(socket: ServerConnection) -> None:
        connections.append(socket)
        async for message in socket:
            frame = json.loads(message)
            frames.append(frame)
            assert len(frames) <= 2, "Runtime must not retry the local test responses"
            if len(frames) == 2 and outcome == "disconnected":
                await socket.close(1011, "synthetic upstream failure")
            elif len(frames) == 2 and outcome == "timeout":
                await socket.wait_closed()
            else:
                await respond(socket, len(frames), request_tool=outcome == "tool_budget_exceeded")

    async def image(invocation: ToolInvocation) -> ToolResult:
        tools_called.append(invocation.tool_name)
        return ToolResult(
            text_result_for_llm="In-memory image; no desktop access.",
            binary_results_for_llm=[
                ToolBinaryResult(data=PNG, mime_type="image/png", type="image")
            ],
        )

    try:
        async with serve(upstream, "127.0.0.1", 0) as server:
            agent = CopilotEval(
                model="offline-model",
                client_mode="empty",
                instructions="Offline system prompt.",
                system_message_mode="replace",
                working_directory=str(tmp_path),
                reasoning_effort="medium",
                audit_requests=True,
                image_detail="high",
                max_tool_calls=1,
                max_retries=0,
                timeout_s=5 if outcome == "timeout" else 20,
                allowed_tools=["memory_image"],
                extra_config={
                    "model_capabilities": ModelCapabilitiesOverride(
                        supports=ModelSupportsOverride(vision=True, reasoning_effort=True)
                    ),
                    "tools": [
                        Tool(
                            "memory_image",
                            "Return an in-memory image.",
                            image,
                            parameters={"type": "object", "properties": {}},
                        )
                    ],
                    "provider": {
                        "type": "openai",
                        "base_url": f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}",
                        "api_key": "offline-provider-token",
                        "wire_api": "responses",
                        "transport": "websockets",
                    },
                },
            )
            result = await copilot_eval(agent, "Read the in-memory image and report ready.")
            if outcome == "completed":
                assert result.success, result.error
                assert result.stop_reason == "completed"
                assert result.evidence_complete, result.capture_errors
            else:
                assert not result.success
                expected = "request_audit_error" if outcome == "disconnected" else outcome
                assert result.stop_reason == expected, result.error
                assert result.usage
                if outcome == "disconnected":
                    assert not result.evidence_complete
            assert tools_called == ["memory_image"]
            assert result.tool_calls_admitted == 1
            assert result.usage[0].input_tokens == 10
            assert result.usage[0].output_tokens == 5
            assert len(connections) == 1
            assert len(frames) == len(result.request_audit) == 2
            assert frames[1]["previous_response_id"] == "response-1"
            first, second = result.request_audit
            assert first.model == second.model == "offline-model"
            assert first.tool_names == second.tool_names == ["memory_image"]
            assert first.reasoning_effort == second.reasoning_effort == "medium"
            assert first.image_count == 0
            assert second.image_count == 1, json.dumps(frames[1])
            assert second.image_details == ["high"]
            assert first.instructions_sha256 == second.instructions_sha256
            assert '"detail": "high"' in json.dumps(frames[1])
            native = _convert_to_aitest(agent, result)
            assert native is not None
            converted = serialize_dataclass(native[0])
            assert converted["request_audit"][1]["image_details"] == ["high"]
            audit_json = json.dumps(converted["request_audit"])
            assert PNG not in audit_json
            assert "offline-provider-token" not in audit_json
            assert "Offline system prompt." not in audit_json
    finally:
        await asyncio.to_thread(api.shutdown)
        api.server_close()
        thread.join()
