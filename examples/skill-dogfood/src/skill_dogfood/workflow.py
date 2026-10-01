"""A consumer test workflow using the framework's fixtures and native evidence."""

from __future__ import annotations

import ast
import asyncio
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_skill_engineering.copilot import CopilotEval, CopilotResult
from pytest_skill_engineering.reporting import SuiteReport, load_suite_report
from skill_dogfood.application import inspect_cli, seed_application
from skill_dogfood.consumer import MODEL

EvalRun = Callable[[CopilotEval, str], Awaitable[CopilotResult]]
RecordProperty = Callable[[str, Any], None]
Variant = Literal["without-skill", "with-skill"]
SYSTEM_PROMPT = (
    "Work on the customer's invoice project using only the supplied project tools. "
    "Read the project requirements, API guidance, and any available skill guidance. "
    "Write only the file authorized for the current task. Do not execute commands, "
    "install packages, change criteria, or create another model runner."
)
AUTHOR_TASK = (
    "Write a meaningful pytest-skill-engineering test for this invoice CLI in "
    "test_invoice.py. Use the provided project fixtures and check real output, "
    "including the stated rounding rule. Follow the README. Author the test only; "
    "the customer will execute it."
)
REPAIR_TASK = (
    "The customer ran your unchanged test. Read before.json, the project source, "
    "and requirements. Investigate the actual failure and fix only invoice_cli.py. "
    "Do not change tests, evidence, or criteria. Do not run paid tests yourself."
)
API_GUIDANCE = """# Available test API

The following are separate pytest fixtures, requested as test parameters:
- invoice_eval: the trusted preconfigured CopilotEval.
- invoice_task: the string "Use the invoice tool for a subtotal of $0.05 with
  10 percent tax."
- copilot_eval: the framework's async execution fixture.
- invoice_output: a callable taking no arguments, returning the dictionary
  actually printed by the invoice command.
- record_property: pytest's check-recording function.

Await copilot_eval(invoice_eval, invoice_task) before calling invoice_output().
result.success means session completion, not invoice correctness.
Use ordinary assertions against that output and record_property(name, value)
with JSON-compatible values. The user request is supplied by invoice_task.
Exactly one framework execution and one test function are permitted.
"""


def prepare_historical_skill(root: Path, workspace: Path) -> Path:
    fixture = root / "examples" / "skill-dogfood" / "fixtures" / "retired-companion"
    skill = workspace / "historical-skill"
    (skill / "references").mkdir(parents=True, exist_ok=False)
    (skill / "SKILL.md").write_bytes((fixture / "instructions.txt").read_bytes())
    for name in ("test-patterns.md", "investigation.md"):
        (skill / "references" / name).write_bytes(
            (fixture / "references" / Path(name).with_suffix(".txt")).read_bytes()
        )
    return skill


def validate_authored_test(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tests = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)]
    if len(tests) != 1 or not tests[0].name.startswith("test_"):
        raise ValueError("Author exactly one async test function")
    if any(isinstance(node, ast.ClassDef) for node in tree.body):
        raise ValueError("Test classes are not permitted")
    if any(
        isinstance(node, ast.FunctionDef) and (node.name.startswith("test_") or node.decorator_list)
        for node in tree.body
    ):
        raise ValueError("Additional tests and fixture definitions are not permitted")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name not in {"decimal", "hashlib", "json", "pytest"} for alias in node.names
            ):
                raise ValueError("Only decimal, hashlib, json, and pytest imports are permitted")
        if isinstance(node, ast.ImportFrom):
            allowed = {
                "__future__": {"annotations"},
                "decimal": {"Decimal", "ROUND_HALF_UP"},
                "hashlib": {"sha256"},
                "pytest_skill_engineering.copilot": {"CopilotEval", "CopilotResult"},
            }
            if node.module not in allowed or any(
                alias.name not in allowed[node.module] for alias in node.names
            ):
                raise ValueError("Direct SDK imports and alternate runners are not permitted")
        if isinstance(node, ast.Attribute) and (
            node.attr.startswith("__")
            or node.attr
            in {
                "skip",
                "xfail",
                "importorskip",
                "parametrize",
                "read_bytes",
                "read_text",
                "write_bytes",
                "write_text",
                "unlink",
                "open",
            }
        ):
            raise ValueError("Introspection, extra cases, skips, and file I/O are not permitted")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {
                "exec",
                "eval",
                "compile",
                "open",
                "__import__",
                "getattr",
                "setattr",
            }:
                raise ValueError("Dynamic execution and direct file access are not permitted")
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "copilot_eval"
    ]
    if len(calls) != 1:
        raise ValueError("Use the copilot_eval fixture exactly once")


def project_tools(
    readable: dict[str, Path],
    writable: dict[str, Path],
    reads: list[str],
) -> list[Tool]:
    def arguments(invocation: ToolInvocation) -> dict[str, Any]:
        if not isinstance(invocation.arguments, dict):
            raise ValueError("Tool arguments must be an object")
        return invocation.arguments

    async def read(invocation: ToolInvocation) -> ToolResult:
        args = arguments(invocation)
        name = args.get("path")
        if not isinstance(name, str) or name not in readable or set(args) != {"path"}:
            raise ValueError("Read only a listed project or guidance file")
        content = readable[name].read_text(encoding="utf-8")
        reads.append(name)
        return ToolResult(text_result_for_llm=content)

    async def write(invocation: ToolInvocation) -> ToolResult:
        args = arguments(invocation)
        name, content = args.get("path"), args.get("content")
        if (
            not isinstance(name, str)
            or name not in writable
            or not isinstance(content, str)
            or not content.strip()
            or set(args) != {"path", "content"}
        ):
            raise ValueError("Write only the authorized file with nonempty text")
        writable[name].write_text(content, encoding="utf-8")
        return ToolResult(text_result_for_llm=f"Saved {name}")

    return [
        Tool(
            name="project_read",
            description="Read a project or available guidance file by its exact listed name.",
            handler=read,
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "enum": list(readable)}},
                "required": ["path"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="project_write",
            description="Write the file authorized for this task.",
            handler=write,
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "enum": list(writable)},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        ),
    ]


def workflow_eval(
    variant: Variant,
    phase: str,
    project: Path,
    skill: Path,
    tools: list[Tool],
    *,
    system_prompt: str,
    name_prefix: str,
) -> CopilotEval:
    return CopilotEval(
        name=f"{name_prefix}-{variant}-{phase}",
        model=MODEL,
        instructions=system_prompt,
        client_mode="empty",
        working_directory=str(project),
        timeout_s=180,
        max_tool_calls=24,
        audit_requests=True,
        skill_directories=[str(skill)] if variant == "with-skill" else [],
        disabled_skills=[] if variant == "with-skill" else ["pytest-skill-engineering"],
        allowed_tools=[tool.name for tool in tools],
        extra_config={"tools": tools},
    )


def run_consumer(
    project: Path, evidence: Path, test_filename: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(project / test_filename),
            "-c",
            str(project / "pyproject.toml"),
            "-o",
            "addopts=",
            "-q",
            f"--aitest-json={evidence}",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=240,
    )


def _check_consumer(
    run: subprocess.CompletedProcess[str],
    evidence: Path,
    *,
    repaired: bool,
) -> SuiteReport:
    assert evidence.is_file(), run.stdout + run.stderr
    suite = load_suite_report(evidence)
    assert len(suite.tests) == 1, "Exactly one consumer execution is required"
    case = suite.tests[0]
    assert case.eval_result is not None, run.stdout + run.stderr
    result = case.eval_result
    assert result.success and result.evidence_complete, result.error
    assert result.configuration is not None, "Prepared session settings were not captured"
    assert result.configuration["model"] == MODEL
    calls = [call for turn in result.turns for call in turn.tool_calls]
    assert len(calls) == 1 and calls[0].name == "invoice"
    assert calls[0].arguments == {"subtotal": "0.05", "tax_percent": "10"}
    assert calls[0].evidence_complete and calls[0].success and calls[0].result is not None
    receipts = [value for name, value in case.properties if name == "cli_response"]
    expected = {
        "subtotal_cents": 5,
        "tax_cents": int(repaired),
        "total_cents": 6 if repaired else 5,
    }
    assert receipts == [expected], "Require the real command's business output"
    assert run.returncode == (0 if repaired else 1), run.stdout + run.stderr
    assert case.outcome == ("passed" if repaired else "failed")
    if not repaired:
        assert case.error and "AssertionError" in case.error, run.stdout + run.stderr
    return suite


async def run_workflow(
    *,
    copilot_eval: EvalRun,
    record_property: RecordProperty,
    root: Path,
    workspace: Path,
    variant: Variant,
) -> None:
    project = workspace / "consumer"
    seed_application(project)
    (project / "API.md").write_text(API_GUIDANCE, encoding="utf-8")
    (project / "conftest.py").write_text(
        'pytest_plugins = ["skill_dogfood.consumer"]\n', encoding="utf-8"
    )
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nasyncio_mode = "auto"\n', encoding="utf-8"
    )
    protected = {
        name: (project / name).read_bytes()
        for name in ("README.md", "API.md", "conftest.py", "pyproject.toml")
    }
    starting = (project / "invoice_cli.py").read_bytes()
    evidence_dir = root / "aitest-reports" / "skill-dogfood" / variant / uuid4().hex
    evidence_dir.mkdir(parents=True)
    record_property("comparison_variant", variant)
    record_property("evidence_directory", str(evidence_dir))
    readable = {name: project / name for name in (*protected, "invoice_cli.py")}
    skill = prepare_historical_skill(root, workspace)
    if variant == "with-skill":
        readable.update(
            {
                "SKILL.md": skill / "SKILL.md",
                "test-patterns.md": skill / "references" / "test-patterns.md",
                "investigation.md": skill / "references" / "investigation.md",
            }
        )
    authored = project / "test_invoice.py"
    author_reads: list[str] = []
    tools = project_tools(readable, {"test_invoice.py": authored}, author_reads)
    result = await copilot_eval(
        workflow_eval(
            variant,
            "author",
            project,
            skill,
            tools,
            system_prompt=SYSTEM_PROMPT,
            name_prefix="dogfood",
        ),
        AUTHOR_TASK,
    )
    record_property("author_guidance_reads", author_reads)
    assert result.success and result.evidence_complete, result.error
    assert (project / "invoice_cli.py").read_bytes() == starting
    assert all((project / name).read_bytes() == data for name, data in protected.items())
    if variant == "with-skill":
        assert "SKILL.md" in author_reads, "Require actual access to the historical fixture"
    validate_authored_test(authored)
    unchanged_test = authored.read_bytes()
    before = evidence_dir / "before.json"
    run = await asyncio.to_thread(run_consumer, project, before, "test_invoice.py")
    record_property(
        "before_consumer",
        {
            "exit_code": run.returncode,
            "evidence": str(before),
            "stdout": run.stdout,
            "stderr": run.stderr,
        },
    )
    _check_consumer(run, before, repaired=False)
    assert authored.read_bytes() == unchanged_test
    assert (project / "invoice_cli.py").read_bytes() == starting
    assert all((project / name).read_bytes() == data for name, data in protected.items())
    before_bytes = before.read_bytes()
    readable.update({"test_invoice.py": authored, "before.json": before})
    repair_reads: list[str] = []
    tools = project_tools(readable, {"invoice_cli.py": project / "invoice_cli.py"}, repair_reads)
    result = await copilot_eval(
        workflow_eval(
            variant,
            "repair",
            project,
            skill,
            tools,
            system_prompt=SYSTEM_PROMPT,
            name_prefix="dogfood",
        ),
        REPAIR_TASK,
    )
    record_property("repair_guidance_reads", repair_reads)
    assert result.success and result.evidence_complete, result.error
    assert "before.json" in repair_reads, "Require inspection of the real failure evidence"
    if variant == "with-skill":
        assert "SKILL.md" in repair_reads, "Require actual skill access during investigation"
    assert authored.read_bytes() == unchanged_test
    assert before.read_bytes() == before_bytes
    assert all((project / name).read_bytes() == data for name, data in protected.items())
    observed = await asyncio.to_thread(inspect_cli, project)
    record_property("independent_cli_verification", observed)
    assert all(case["passed"] for case in observed), observed
    after = evidence_dir / "after.json"
    run = await asyncio.to_thread(run_consumer, project, after, "test_invoice.py")
    record_property(
        "after_consumer",
        {
            "exit_code": run.returncode,
            "evidence": str(after),
            "stdout": run.stdout,
            "stderr": run.stderr,
        },
    )
    _check_consumer(run, after, repaired=True)
    assert authored.read_bytes() == unchanged_test
    assert before.read_bytes() == before_bytes
    assert all((project / name).read_bytes() == data for name, data in protected.items())
