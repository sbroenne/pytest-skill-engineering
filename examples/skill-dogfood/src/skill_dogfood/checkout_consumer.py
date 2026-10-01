"""Trusted fixtures for the imported-order consumer test."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_skill_engineering.copilot import CopilotEval
from skill_dogfood.checkout import TASK, observe_checkout
from skill_dogfood.consumer import MODEL, EvalRun, guard_execution


@pytest.fixture
def checkout_task() -> str:
    return TASK


@pytest.fixture
def checkout_inputs(request: pytest.FixtureRequest) -> dict[str, dict[str, str]]:
    project = Path(str(request.node.path)).parent
    inputs = {}
    for name in ("order.csv", "other.csv", "conflict.csv"):
        contents = (project / name).read_bytes()
        inputs[name] = {
            "csv_text": contents.decode("utf-8"),
            "fingerprint": hashlib.sha256(contents).hexdigest(),
        }
    return inputs


@pytest.fixture
def checkout_state() -> list[dict[str, Any]]:
    return []


@pytest.fixture
def checkout_observation(checkout_state: list[dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    def observed() -> dict[str, Any]:
        if len(checkout_state) != 1:
            raise ValueError("Exactly one actual checkout workflow is required")
        return copy.deepcopy(checkout_state[0])

    return observed


@pytest.fixture
def checkout_eval(
    request: pytest.FixtureRequest,
    checkout_state: list[dict[str, Any]],
    record_property: Callable[[str, Any], None],
) -> CopilotEval:
    project = Path(str(request.node.path)).parent
    used = False

    async def checkout(invocation: ToolInvocation) -> ToolResult:
        nonlocal used
        if used or invocation.arguments != {"order_file": "order.csv", "request_id": "checkout-1"}:
            raise ValueError("Only the supplied checkout workflow may run, once")
        used = True
        observed = await asyncio.to_thread(observe_checkout, project)
        checkout_state.append(observed)
        record_property("actual_checkout", observed)
        return ToolResult(text_result_for_llm=json.dumps(observed))

    tool = Tool(
        name="checkout",
        description="Run the order workflow and capture actual CLI replies and ledger snapshots.",
        handler=checkout,
        parameters={
            "type": "object",
            "properties": {
                "order_file": {"type": "string", "enum": ["order.csv"]},
                "request_id": {"type": "string", "enum": ["checkout-1"]},
            },
            "required": ["order_file", "request_id"],
            "additionalProperties": False,
        },
    )
    return CopilotEval(
        name="checkout-consumer",
        model=MODEL,
        client_mode="empty",
        working_directory=str(project),
        instructions="Use the checkout tool once for this task.",
        timeout_s=120,
        max_tool_calls=4,
        allowed_tools=["checkout"],
        extra_config={"tools": [tool]},
    )


@pytest.fixture
def copilot_eval(copilot_eval: EvalRun, checkout_eval: CopilotEval) -> EvalRun:
    return guard_execution(copilot_eval, checkout_eval, TASK)
