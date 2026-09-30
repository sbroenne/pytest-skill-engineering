"""Trusted consumer fixtures. All Copilot execution stays in copilot_eval."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.copilot.result import CopilotResult
from skill_dogfood.application import INVOICE_TASK, read_invoice, run_invoice

MODEL = "gpt-5.6-luna"
EvalRun = Callable[[CopilotEval, str], Awaitable[CopilotResult]]


@pytest.fixture
def invoice_task() -> str:
    return INVOICE_TASK


@pytest.fixture
def invoice_state() -> list[dict[str, int]]:
    return []


@pytest.fixture
def invoice_output(invoice_state: list[dict[str, int]]) -> Callable[[], dict[str, int]]:
    def observed() -> dict[str, int]:
        if len(invoice_state) != 1:
            raise ValueError("Exactly one real invoice invocation is required")
        return invoice_state[0].copy()

    return observed


@pytest.fixture
def invoice_eval(
    request: pytest.FixtureRequest,
    invoice_state: list[dict[str, int]],
    record_property: Callable[[str, Any], None],
) -> CopilotEval:
    project = Path(str(request.node.path)).parent
    return create_invoice_eval(project, invoice_state, record_property)


def create_invoice_eval(
    project: Path,
    invoice_state: list[dict[str, int]],
    record_property: Callable[[str, Any], None],
) -> CopilotEval:
    used = False

    async def invoice(invocation: ToolInvocation) -> ToolResult:
        nonlocal used
        args = invocation.arguments
        if args != {"subtotal": "0.05", "tax_percent": "10"} or used:
            raise ValueError("Only the requested invoice may be executed, exactly once")
        used = True
        run = await asyncio.to_thread(run_invoice, project, "0.05", "10")
        if run.returncode != 0 or run.stderr:
            raise ValueError(f"Invoice command failed: {run.returncode}: {run.stderr}")
        payload = read_invoice(run.stdout)
        invoice_state.append(payload)
        record_property("cli_response", payload)
        return ToolResult(text_result_for_llm=json.dumps(payload))

    tool = Tool(
        name="invoice",
        description="Compute the requested invoice by executing the project's real CLI.",
        handler=invoice,
        parameters={
            "type": "object",
            "properties": {
                "subtotal": {"type": "string"},
                "tax_percent": {"type": "string"},
            },
            "required": ["subtotal", "tax_percent"],
            "additionalProperties": False,
        },
    )
    return CopilotEval(
        name="invoice-consumer",
        model=MODEL,
        client_mode="empty",
        working_directory=str(project),
        instructions="Use the supplied invoice tool once for the requested invoice.",
        timeout_s=120,
        max_tool_calls=4,
        allowed_tools=["invoice"],
        extra_config={"tools": [tool]},
    )


@pytest.fixture
def copilot_eval(copilot_eval: EvalRun, invoice_eval: CopilotEval) -> EvalRun:
    return guard_execution(copilot_eval, invoice_eval, INVOICE_TASK)


def guard_execution(execute: EvalRun, invoice_eval: CopilotEval, task: str) -> EvalRun:
    used = False

    async def once(agent: CopilotEval, prompt: str) -> CopilotResult:
        nonlocal used
        if used or agent is not invoice_eval or prompt != task:
            raise ValueError("Use the supplied eval and task for exactly one framework execution")
        used = True
        return await execute(agent, prompt)

    return once
