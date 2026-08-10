"""Deterministic tests for custom-agent dispatch polyfills."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from pytest_skill_engineering.copilot.contracts import CopilotEvalConfig
from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.events import EventMapper
from pytest_skill_engineering.copilot.personas import _make_subagent_dispatch_tool
from pytest_skill_engineering.copilot.result import CopilotResult, Turn


async def test_subagent_dispatch_preserves_exact_tools_and_merges_mcp_servers(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_copilot(agent: CopilotEvalConfig, prompt: str) -> CopilotResult:
        captured["agent"] = agent
        captured["prompt"] = prompt
        return CopilotResult(turns=[Turn(role="assistant", content="done")], success=True)

    parent = CopilotEval(
        name="orchestrator",
        model="gpt-5.4-mini",
        reasoning_effort="high",
        instructions="Delegate file writes.",
        working_directory=str(tmp_path),
        allowed_tools=["read_file", "runSubagent"],
        mcp_servers={
            "shared": {"command": "uvx", "args": ["shared-parent"]},
            "parent-only": {"command": "uvx", "args": ["parent"]},
        },
    )
    mapper = EventMapper()
    dispatch_tool = _make_subagent_dispatch_tool(
        "runSubagent",
        parent,
        [
            {
                "name": "file-writer",
                "prompt": "Write the requested file.",
                "tools": ["create_file", "insert_edit_into_file"],
                "mcp_servers": {
                    "shared": {"command": "uvx", "args": ["shared-child"]},
                    "child-only": {"command": "uvx", "args": ["child"]},
                },
            }
        ],
        mapper,
        fake_run_copilot,
    )

    handler = cast(Any, dispatch_tool.handler)
    tool_result = await handler(
        cast(
            Any,
            SimpleNamespace(
                tool_call_id="call-1",
                arguments={"agentSlug": "file-writer", "prompt": "Create hello.py"},
            ),
        )
    )
    result = mapper.build()

    sub_agent = captured["agent"]
    assert isinstance(sub_agent, CopilotEval)
    assert captured["prompt"] == "Create hello.py"
    assert sub_agent.name == "file-writer"
    assert sub_agent.instructions == "Write the requested file."
    assert sub_agent.allowed_tools == ["create_file", "insert_edit_into_file"]
    assert sub_agent.excluded_tools is None
    assert set(sub_agent.mcp_servers) == {"shared", "parent-only", "child-only"}
    assert sub_agent.mcp_servers["shared"].get("args") == ["shared-child"]
    assert tool_result.result_type == "success"
    assert tool_result.text_result_for_llm == "done"
    assert [(inv.invocation_id, inv.name, inv.status) for inv in result.subagent_invocations] == [
        ("call-1", "file-writer", "completed")
    ]
