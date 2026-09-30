"""Per-run dispatch limits and ownership of custom tool work."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable
from dataclasses import replace
from typing import Any, TypeVar, cast

from copilot.session import PreToolUseHookInput, PreToolUseHookOutput
from copilot.tools import Tool, ToolInvocation, ToolResult

T = TypeVar("T")
logger = logging.getLogger(__name__)


async def resolve(value: T | Awaitable[T]) -> T:
    return await value if inspect.isawaitable(value) else cast(T, value)


class RunControls:
    """Close dispatch before aborting, and drain owned work before returning."""

    def __init__(self, max_tool_calls: int | None) -> None:
        self.limit = max_tool_calls
        self.admitted = 0
        self.completed = 0
        self.started = 0
        self.handlers_started = 0
        self.handlers_finished = 0
        self.closed = False
        self._budget_exhausted = False
        self._started_call_ids: list[str] = []
        self._completed_call_ids: set[str] = set()
        self._handler_started_call_ids: set[str] = set()
        self._handler_finished_call_ids: set[str] = set()
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
                    logger.info(
                        "Tool budget closed admission: admitted=%d started=%d completed=%d",
                        self.admitted,
                        self.started,
                        self.completed,
                    )
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

    def observe(self, event: Any) -> bool:
        """Observe tool lifecycle and report when the budget barrier releases."""
        event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
        if event_type == "tool.execution_start":
            call_id = _event_data_field(event, "tool_call_id", "")
            if call_id and call_id not in self._started_call_ids:
                self._started_call_ids.append(call_id)
                self.started += 1
            return False
        if event_type != "tool.execution_complete":
            return False
        call_id = _event_data_field(event, "tool_call_id", "")
        if call_id and call_id not in self._completed_call_ids:
            self._completed_call_ids.add(call_id)
            self.completed += 1
        return self._signal_budget_when_complete()

    def _signal_budget_when_complete(self) -> bool:
        if (
            self._budget_exhausted
            and self.started >= self.admitted
            and set(self._started_call_ids) <= self._completed_call_ids
            and not self.budget_exceeded.is_set()
        ):
            logger.info(
                "Tool budget completion barrier released: admitted=%d started=%d completed=%d",
                self.admitted,
                self.started,
                self.completed,
            )
            self.budget_exceeded.set()
            return True
        return False

    def wrap(self, tool: Tool) -> Tool:
        handler = tool.handler
        if handler is None:
            return tool

        async def invoke(invocation: ToolInvocation) -> ToolResult:
            async def execute() -> ToolResult:
                call_id = invocation.tool_call_id
                self._handler_started_call_ids.add(call_id)
                self.handlers_started += 1
                try:
                    return await resolve(handler(invocation))
                finally:
                    self._handler_finished_call_ids.add(call_id)
                    self.handlers_finished += 1

            task = asyncio.create_task(execute())
            self.active.add(task)
            try:
                # SDK abort/disconnect may cancel the RPC callback, not the action.
                return await asyncio.shield(task)
            finally:
                if task.done():
                    self.active.discard(task)

        return replace(tool, handler=invoke)

    def incomplete_diagnostics(self, *, abort_phase: str) -> list[str]:
        """Return safe lifecycle details for started calls missing SDK completion."""
        diagnostics = []
        for ordinal, call_id in enumerate(self._started_call_ids, 1):
            if call_id in self._completed_call_ids:
                continue
            handler_state = (
                "finished"
                if call_id in self._handler_finished_call_ids
                else "started"
                if call_id in self._handler_started_call_ids
                else "not_started"
            )
            diagnostics.append(
                "Tool lifecycle incomplete: "
                f"call={call_id}, start_ordinal={ordinal}, admitted={self.admitted}, "
                f"handler={handler_state}, sdk_completion=missing, abort_phase={abort_phase}"
            )
        return diagnostics

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


def _event_data_field(event: Any, name: str, default: T) -> T:
    data = getattr(event, "data", None)
    if isinstance(data, dict):
        camel_name = "".join(
            part if index == 0 else part.title() for index, part in enumerate(name.split("_"))
        )
        return cast(T, data.get(name, data.get(camel_name, default)))
    return cast(T, getattr(data, name, default))
