"""Per-run dispatch limits and ownership of custom tool work."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable
from dataclasses import replace
from typing import Any, TypeVar, cast

from copilot.session import PreToolUseHookInput, PreToolUseHookOutput
from copilot.tools import Tool, ToolInvocation, ToolResult

T = TypeVar("T")


async def resolve(value: T | Awaitable[T]) -> T:
    return await value if inspect.isawaitable(value) else cast(T, value)


class RunControls:
    """Close dispatch before aborting, and drain owned work before returning."""

    def __init__(self, max_tool_calls: int | None) -> None:
        self.limit = max_tool_calls
        self.admitted = 0
        self.completed = 0
        self.closed = False
        self._budget_exhausted = False
        self.budget_exceeded = asyncio.Event()
        self.failed = asyncio.Event()
        self.error: str | None = None
        self.lock = asyncio.Lock()
        self.active: set[asyncio.Task[ToolResult]] = set()

    def install(self, config: dict[str, Any], caller_hooks: dict[str, Any]) -> None:
        hooks = dict(config.get("hooks") or {})
        pre_hooks = []
        for source in (caller_hooks, hooks):
            pre = source.get("on_pre_tool_use")
            if pre is not None and pre not in pre_hooks:
                pre_hooks.append(pre)
        for key, handler in caller_hooks.items():
            if key == "on_pre_tool_use":
                continue
            if key in hooks and hooks[key] is not handler:
                raise ValueError(f"Persona replaced caller hook {key}; compose it explicitly")
            hooks[key] = handler

        async def before(
            data: PreToolUseHookInput, context: dict[str, str]
        ) -> PreToolUseHookOutput | None:
            async with self.lock:
                if self.closed:
                    return {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Eval stopped",
                    }
                if self.limit is not None and self.admitted >= self.limit:
                    self.closed = True
                    self._budget_exhausted = True
                    self._signal_budget_when_complete()
                    return {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Eval tool-call budget exhausted",
                    }
                combined: PreToolUseHookOutput = {}
                for hook in pre_hooks:
                    try:
                        output = await resolve(hook(data, context))
                        if output is not None and (
                            not isinstance(output, dict)
                            or output.get("permissionDecision")
                            not in (None, "allow", "deny", "ask")
                        ):
                            raise ValueError("Invalid pre-tool guard output")
                    except Exception as exc:
                        self.error = f"Pre-tool guard failed: {type(exc).__name__}"
                        self.closed = True
                        self.failed.set()
                        return {
                            "permissionDecision": "deny",
                            "permissionDecisionReason": self.error,
                        }
                    if output:
                        must_ask = combined.get("permissionDecision") == "ask"
                        previous_context = combined.get("additionalContext")
                        combined.update(output)
                        if output.get("permissionDecision") == "deny":
                            return combined
                        if must_ask:
                            combined["permissionDecision"] = "ask"
                        if previous_context and output.get("additionalContext"):
                            combined["additionalContext"] = (
                                previous_context + "\n" + output["additionalContext"]
                            )
                        if "modifiedArgs" in output:
                            data = {**data, "toolArgs": output["modifiedArgs"]}
                # A timeout may have closed dispatch while a caller hook awaited.
                if self.closed:
                    return {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Eval stopped",
                    }
                self.admitted += 1
                return combined or None

        hooks["on_pre_tool_use"] = before
        config["hooks"] = hooks
        config["tools"] = [self.wrap(tool) for tool in config.get("tools", [])]

    def observe(self, event: Any) -> None:
        """Release a pending budget stop only after admitted calls complete."""
        event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
        if event_type != "tool.execution_complete":
            return
        self.completed += 1
        self._signal_budget_when_complete()

    def _signal_budget_when_complete(self) -> None:
        if self._budget_exhausted and self.completed >= self.admitted:
            self.budget_exceeded.set()

    def wrap(self, tool: Tool) -> Tool:
        handler = tool.handler
        if handler is None:
            return tool

        async def invoke(invocation: ToolInvocation) -> ToolResult:
            async def execute() -> ToolResult:
                return await resolve(handler(invocation))

            task = asyncio.create_task(execute())
            self.active.add(task)
            try:
                # SDK abort/disconnect may cancel the RPC callback, not the action.
                return await asyncio.shield(task)
            finally:
                if task.done():
                    self.active.discard(task)

        return replace(tool, handler=invoke)

    async def drain(self) -> list[str]:
        """Never release a trial while its local handlers can still act."""
        self.closed = True
        tasks = list(self.active)
        if not tasks:
            return []
        outcomes = await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
        self.active.difference_update(tasks)
        return [
            f"Tool handler failed during cleanup: {type(outcome).__name__}"
            for outcome in outcomes
            if isinstance(outcome, BaseException)
        ]
