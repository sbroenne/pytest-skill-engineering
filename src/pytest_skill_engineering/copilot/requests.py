"""Privacy-preserving evidence from the SDK's outbound model requests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from copilot import CopilotRequestContext, CopilotRequestHandler, CopilotWebSocketHandler

ImageDetail = Literal["auto", "low", "high"]


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


class RequestAuditHandler(CopilotRequestHandler):
    """Inspect HTTP inference requests; reject transports we cannot audit."""

    def __init__(self, *, image_detail: ImageDetail | None, audit: bool) -> None:
        self.image_detail: ImageDetail | None = image_detail
        self.audit = audit
        self.records: list[RequestAudit] = []
        self.observed_requests = 0
        self.failed = asyncio.Event()
        self.error: str | None = None
        self.http: httpx.AsyncClient | None = None

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
        self.fail("Unsupported request audit transport: WebSocket; use HTTP inference")
        raise ValueError(self.error)

    async def aclose(self) -> None:
        if self.http is not None:
            await self.http.aclose()
