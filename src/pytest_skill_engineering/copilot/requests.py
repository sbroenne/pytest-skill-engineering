"""Privacy-preserving evidence from the SDK's outbound model requests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from copilot import (
    CopilotRequestContext,
    CopilotRequestHandler,
    CopilotWebSocketCloseStatus,
    CopilotWebSocketForwarder,
    CopilotWebSocketHandler,
)

ImageDetail = Literal["auto", "low", "high"]
TransportPhase = Literal["open", "send", "receive"]


@dataclass(slots=True, frozen=True)
class RequestAudit:
    """Observed wire values, never inferred from the eval configuration."""

    request_id: str
    model: str
    tool_names: list[str]
    reasoning_effort: str | None
    image_details: list[str | None]
    image_count: int
    instructions_sha256: str


def _transport_failure_message(phase: TransportPhase, error: BaseException) -> str:
    """Describe transport failures without retaining provider messages or request data."""
    details: list[str] = []
    if isinstance(error, RuntimeError):
        category = {
            "Copilot request response used after RPC connection closed.": "sdk_rpc_closed",
            "Copilot request was cancelled by the runtime.": "runtime_cancelled",
            "Copilot request response write() called after end()/error().": "response_finished",
        }.get(str(error), "runtime_error")
        details.append(f"category={category}")
    received = getattr(error, "rcvd", None)
    close_code = getattr(received, "code", None)
    if isinstance(close_code, int):
        details.append(f"close_code={close_code}")
    if error.__cause__ is not None:
        details.append(f"cause={type(error.__cause__).__name__}")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"WebSocket transport {phase} failed: {type(error).__name__}{suffix}"


def _instruction_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if all(
            isinstance(part, dict)
            and part.get("type") in ("text", "input_text")
            and isinstance(part.get("text"), str)
            for part in content
        ):
            return "\n\n".join(part["text"] for part in content)
    raise ValueError("Unsupported system/developer instruction content")


def _audit_payload(payload: Any, request_id: str, detail: ImageDetail | None) -> RequestAudit:
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("model"), str)
        or not payload["model"]
    ):
        raise ValueError("Unsupported model request: missing model")
    if "system" in payload or ("messages" in payload and "input" in payload):
        raise ValueError("Unsupported model request schema")
    instructions: list[str] = []
    if "messages" in payload:
        messages = payload["messages"]
        effort = payload.get("reasoning_effort")
    elif "input" in payload:
        messages = payload["input"]
        if isinstance(messages, str):
            messages = []
        reasoning = payload.get("reasoning")
        if reasoning is not None and not isinstance(reasoning, dict):
            raise ValueError("Unsupported reasoning configuration")
        effort = reasoning.get("effort") if reasoning else None
        if payload.get("instructions") is not None:
            instructions.append(_instruction_text(payload["instructions"]))
    else:
        raise ValueError("Unsupported model request: expected messages or input")
    if effort is not None and not isinstance(effort, str):
        raise ValueError("Unsupported reasoning effort")
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        raise ValueError("Unsupported model request messages")
    for message in messages:
        if message.get("role") in ("system", "developer"):
            instructions.append(_instruction_text(message.get("content")))

    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("Unsupported advertised tool list")
    names: list[str] = []
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            raise ValueError("Unsupported advertised tool schema")
        function = tool.get("function", tool)
        if (
            not isinstance(function, dict)
            or not isinstance(function.get("name"), str)
            or not function["name"]
        ):
            raise ValueError("Unsupported advertised tool name")
        names.append(function["name"])

    images: list[str | None] = []

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for part in value:
                visit(part)
        elif isinstance(value, dict):
            kind = value.get("type")
            if kind in ("input_image", "image_url"):
                target = value if kind == "input_image" else value.get("image_url")
                if not isinstance(target, dict):
                    raise ValueError("Unsupported image payload")
                if kind == "image_url" and not isinstance(target.get("url"), str):
                    raise ValueError("Unsupported image URL")
                if kind == "input_image" and not (
                    isinstance(value.get("image_url"), str) or isinstance(value.get("file_id"), str)
                ):
                    raise ValueError("Unsupported input image source")
                if detail is not None:
                    target["detail"] = detail
                actual = target.get("detail")
                if actual not in (None, "auto", "low", "high"):
                    raise ValueError("Unsupported image detail")
                images.append(actual)
                return
            if kind == "image":
                raise ValueError("Unsupported image schema: expected OpenAI image content")
            for part in value.values():
                visit(part)

    visit(messages)
    return RequestAudit(
        request_id=request_id,
        model=payload["model"],
        tool_names=names,
        reasoning_effort=effort,
        image_details=images,
        image_count=len(images),
        instructions_sha256=hashlib.sha256("\n\n".join(instructions).encode("utf-8")).hexdigest(),
    )


class _AuditedWebSocket(CopilotWebSocketForwarder):
    """Audit each Responses message before the SDK forwards it."""

    def __init__(self, context: CopilotRequestContext, owner: RequestAuditHandler) -> None:
        super().__init__(context)
        self.owner = owner

    async def open(self) -> None:
        if self.owner.failed.is_set():
            raise ValueError("Request audit already failed")
        try:
            await super().open()
        except Exception as exc:
            message = _transport_failure_message("open", exc)
            self.owner.fail(message)
            raise ValueError(message) from None

    async def send_request_message(self, data: str | bytes) -> None:
        if self.owner.failed.is_set():
            raise ValueError("Request audit already failed")
        try:
            if not isinstance(data, str):
                raise ValueError("Unsupported WebSocket frame: expected JSON text")
            payload = json.loads(data)
            if not isinstance(payload, dict) or payload.get("type") != "response.create":
                raise ValueError("Unsupported WebSocket frame: expected response.create")
            if "input" not in payload or "messages" in payload:
                raise ValueError("Unsupported WebSocket Responses request")
            if payload.get("previous_response_id") is not None and not all(
                field in payload for field in ("model", "instructions", "tools")
            ):
                raise ValueError("Unsupported continuation: request settings must be explicit")
            record = _audit_payload(payload, self.context.request_id, self.owner.image_detail)
            content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except (ValueError, TypeError, UnicodeError) as exc:
            message = (
                "Unsupported WebSocket request: invalid JSON"
                if isinstance(exc, json.JSONDecodeError)
                else str(exc)
            )
            self.owner.fail(message)
            raise ValueError(message) from None
        if self._upstream is None or self._closed:
            self.owner.fail("WebSocket transport is not open")
            raise ValueError(self.owner.error)
        self.owner.observed_requests += 1
        if self.owner.audit:
            self.owner.records.append(record)
        try:
            await super().send_request_message(content)
        except Exception as exc:
            message = _transport_failure_message("send", exc)
            self.owner.fail(message)
            raise ValueError(message) from None

    async def close(self, status: CopilotWebSocketCloseStatus | None = None) -> None:
        if status is not None and status.error is not None:
            message = _transport_failure_message("receive", status.error)
            self.owner.fail(message)
            status = CopilotWebSocketCloseStatus(description=message, error=ValueError(message))
        try:
            if self._upstream is not None:
                await self._upstream.close()
        finally:
            await CopilotWebSocketHandler.close(self, status)

    async def aclose(self) -> None:
        try:
            if self._suppress_close_on_dispose:
                if self._upstream is not None:
                    await self._upstream.close()
            else:
                await self.close()
        finally:
            if self._receive_task is not None:
                self._receive_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._receive_task


class RequestAuditHandler(CopilotRequestHandler):
    """Inspect HTTP requests and WebSocket Responses messages before forwarding."""

    def __init__(self, *, image_detail: ImageDetail | None, audit: bool) -> None:
        self.image_detail: ImageDetail | None = image_detail
        self.audit = audit
        self.records: list[RequestAudit] = []
        self.observed_requests = 0
        self.failed = asyncio.Event()
        self.error: str | None = None
        self.http: httpx.AsyncClient | None = None
        self.websockets: list[_AuditedWebSocket] = []

    def fail(self, message: str) -> None:
        self.error = message
        self.failed.set()

    async def send_request(
        self, request: httpx.Request, ctx: CopilotRequestContext
    ) -> httpx.Response:
        if self.failed.is_set():
            raise ValueError("Request audit already failed")
        if request.method == "GET" and not request.url.path.rstrip("/").endswith("/models"):
            self.fail("Unsupported request audit: only model-catalog GET requests may bypass audit")
            raise ValueError(self.error)
        if request.method != "GET":
            try:
                if request.headers.get("content-encoding", "identity") != "identity":
                    raise ValueError("Unsupported compressed model request")
                payload = json.loads(await request.aread())
                record = _audit_payload(payload, ctx.request_id, self.image_detail)
                content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
                headers = [
                    (key, value)
                    for key, value in request.headers.multi_items()
                    if key.lower() not in ("content-length", "transfer-encoding")
                ]
                request = httpx.Request(
                    request.method,
                    request.url,
                    headers=headers,
                    content=content,
                    extensions=request.extensions,
                )
            except (ValueError, TypeError, UnicodeError) as exc:
                # JSON decoding errors can contain pieces of the raw request.
                message = (
                    "Unsupported model request: invalid JSON"
                    if isinstance(exc, json.JSONDecodeError)
                    else str(exc)
                )
                self.fail(message)
                raise ValueError(message) from None
            self.observed_requests += 1
            if self.audit:
                self.records.append(record)
        if self.http is None:
            self.http = httpx.AsyncClient(timeout=None, follow_redirects=False)
        return await self.http.send(request, stream=True)

    async def open_websocket(self, ctx: CopilotRequestContext) -> CopilotWebSocketHandler:
        if self.failed.is_set():
            raise ValueError("Request audit already failed")
        socket = _AuditedWebSocket(ctx, self)
        self.websockets.append(socket)
        return socket

    async def aclose(self) -> None:
        closes = [socket.aclose() for socket in self.websockets]
        if self.http is not None:
            closes.append(self.http.aclose())
        outcomes = await asyncio.gather(*closes, return_exceptions=True)
        errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        if errors:
            raise BaseExceptionGroup("Request transport cleanup failed", errors)
