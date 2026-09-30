from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import pytest
from copilot.tools import Tool, ToolInvocation, ToolResult
from skill_dogfood.application import INVOICE_TASK, seed_application
from skill_dogfood.consumer import MODEL, create_invoice_eval, guard_execution
from skill_dogfood.workflow import _check_consumer, project_tools, run_consumer

from pytest_skill_engineering.copilot import CopilotEval, CopilotResult


async def invoke(tool: Tool, arguments: Any) -> ToolResult:
    assert tool.handler is not None
    result = tool.handler(ToolInvocation(arguments=arguments))
    assert isinstance(result, Awaitable), "These application adapters must be async"
    return await result


async def test_project_tools_preserve_read_only_criteria(tmp_path: Path) -> None:
    criteria = tmp_path / "criteria.md"
    criteria.write_text("Fixed criteria", encoding="utf-8")
    authored = tmp_path / "test_invoice.py"
    reads: list[str] = []
    read, write = project_tools({"criteria.md": criteria}, {"test_invoice.py": authored}, reads)
    result = await invoke(read, {"path": "criteria.md"})
    assert result.text_result_for_llm == "Fixed criteria"
    assert reads == ["criteria.md"]
    await invoke(write, {"path": "test_invoice.py", "content": "authorized text"})
    assert authored.read_text(encoding="utf-8") == "authorized text"
    assert criteria.read_text(encoding="utf-8") == "Fixed criteria"


@pytest.mark.parametrize(
    "arguments",
    [
        {"path": "..\\criteria.md", "content": "changed"},
        {"path": "criteria.md", "content": "changed"},
        {"path": "test_invoice.py", "content": ""},
        {"path": "test_invoice.py", "content": "changed", "extra": True},
        ["test_invoice.py"],
    ],
)
async def test_project_tools_reject_unauthorized_writes(tmp_path: Path, arguments: Any) -> None:
    criteria = tmp_path / "criteria.md"
    criteria.write_text("Fixed criteria", encoding="utf-8")
    authored = tmp_path / "test_invoice.py"
    _, write = project_tools({"criteria.md": criteria}, {"test_invoice.py": authored}, [])
    with pytest.raises(ValueError):
        await invoke(write, arguments)
    assert not authored.exists()
    assert criteria.read_text(encoding="utf-8") == "Fixed criteria"


async def test_project_tools_reject_unlisted_reads(tmp_path: Path) -> None:
    read, _ = project_tools({}, {"test_invoice.py": tmp_path / "test_invoice.py"}, [])
    with pytest.raises(ValueError, match="listed"):
        await invoke(read, {"path": "..\\outside.md"})


async def test_invoice_tool_rejects_concurrent_duplicate_execution(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    seed_application(project)
    state: list[dict[str, int]] = []
    properties: list[tuple[str, Any]] = []
    agent = create_invoice_eval(
        project, state, lambda name, value: properties.append((name, value))
    )
    tool: Tool = agent.extra_config["tools"][0]
    results = await asyncio.gather(
        invoke(tool, {"subtotal": "0.05", "tax_percent": "10"}),
        invoke(tool, {"subtotal": "0.05", "tax_percent": "10"}),
        return_exceptions=True,
    )
    assert not isinstance(results[0], BaseException)
    assert isinstance(results[1], ValueError)
    assert state == [{"subtotal_cents": 5, "tax_cents": 0, "total_cents": 5}]
    assert properties == [("cli_response", state[0])]


async def test_consumer_guard_allows_only_one_framework_execution(tmp_path: Path) -> None:
    agent = create_invoice_eval(tmp_path, [], lambda name, value: None)
    calls: list[tuple[CopilotEval, str]] = []
    captured = CopilotResult()

    async def execute(eval_: CopilotEval, prompt: str) -> CopilotResult:
        calls.append((eval_, prompt))
        return captured

    once = guard_execution(execute, agent, INVOICE_TASK)
    with pytest.raises(ValueError, match="supplied"):
        await once(CopilotEval(name="other", model=MODEL), INVOICE_TASK)
    with pytest.raises(ValueError, match="supplied"):
        await once(agent, "A different task")
    assert calls == []
    assert await once(agent, INVOICE_TASK) is captured
    with pytest.raises(ValueError, match="exactly one"):
        await once(agent, INVOICE_TASK)
    assert calls == [(agent, INVOICE_TASK)]


@pytest.mark.parametrize(
    "source,exit_code",
    [
        ("def test_broken(:\n    pass\n", 2),
        ("async def test_no_execution():\n    assert False, 'not a business check'\n", 1),
    ],
)
def test_consumer_evidence_rejects_failures_without_execution(
    tmp_path: Path, source: str, exit_code: int
) -> None:
    (tmp_path / "test_invoice.py").write_text(source, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nasyncio_mode = "auto"\n', encoding="utf-8"
    )
    evidence = tmp_path / "before.json"
    run = run_consumer(tmp_path, evidence, "test_invoice.py")
    assert run.returncode == exit_code, run.stdout + run.stderr
    with pytest.raises(AssertionError):
        _check_consumer(run, evidence, repaired=False)


def test_default_collection_excludes_live_workflows() -> None:
    project = Path(__file__).resolve().parents[2]
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "test_application.py" in run.stdout
    assert "test_boundaries.py" in run.stdout
    assert "test_workflow.py" not in run.stdout
