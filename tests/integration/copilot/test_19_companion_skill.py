"""Real-Copilot checks of the companion skill, with consumer-owned verification."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
from pytest_skill_engineering.reporting import SuiteReport, generate_json
from pytest_skill_engineering.reporting import TestReport as CaseReport

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot, pytest.mark.skill]
ROOT = Path(__file__).parents[3]
SKILL = ROOT / "skills" / "pytest-skill-engineering"


def _pytest(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(ROOT),
            "python",
            "-m",
            "pytest",
            *args,
            "-o",
            "addopts=",
            "-o",
            "asyncio_mode=auto",
            "-q",
        ],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=180,
    )


async def test_skill_authors_a_runnable_framework_test(copilot_eval, tmp_path, record_property):
    agent = CopilotEval(
        name="companion-test-author",
        model=DEFAULT_MODEL,
        working_directory=str(tmp_path),
        skill_directories=[str(SKILL)],
        instructions="Use the pytest-skill-engineering skill. Author files only; do not run paid tests.",
    )
    result = await copilot_eval(
        agent,
        "Write test_consumer.py with exactly one async pytest test using CopilotEval and "
        "the copilot_eval fixture, model gpt-5.6-luna, and tmp_path as working_directory. "
        "The user task asks Copilot to create calc.py with add(a,b) returning a+b. "
        "Use ordinary assertions and a bounded subprocess to verify add(2,3)==5 and "
        "add(-1,1)==0. Record the independent check with record_property. "
        "Do not execute the test, install anything, create a conftest, mock execution, "
        "or add any separate SDK runner or AI judge. The parent will run this paid case.",
    )
    assert result.success, result.error
    authored = tmp_path / "test_consumer.py"
    source = authored.read_text(encoding="utf-8")
    ast.parse(source)
    assert "CopilotEval" in source and "copilot_eval" in source and "record_property" in source
    for forbidden in ("CopilotClient", "run_copilot", "llm_assert", "llm_score", "unittest.mock"):
        assert forbidden not in source
    evidence = tmp_path / "consumer-results.json"
    run = _pytest(
        tmp_path, str(authored), "--basetemp", str(tmp_path / "run"), f"--aitest-json={evidence}"
    )
    record_property(
        "consumer_verification",
        {"exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr},
    )
    assert run.returncode == 0, run.stdout + run.stderr
    saved = json.loads(evidence.read_text(encoding="utf-8"))
    assert len(saved["tests"]) == 1
    assert saved["tests"][0]["outcome"] == "passed"
    assert saved["tests"][0]["eval_result"]["success"] is True
    outputs = list((tmp_path / "run").rglob("calc.py"))
    assert len(outputs) == 1
    checked = subprocess.run(
        [sys.executable, "-c", "from calc import add; assert add(2,3)==5; assert add(-1,1)==0"],
        cwd=outputs[0].parent,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert checked.returncode == 0, checked.stderr


async def test_skill_investigates_source_without_rewriting_criteria(
    copilot_eval,
    tmp_path,
    record_property,
):
    module = tmp_path / "consumer_tools.py"
    module.write_text(
        "def dollars_to_cents(amount):\n    return round(amount * 100) + 1\n", encoding="utf-8"
    )
    test = tmp_path / "test_money.py"
    test.write_text(
        "from consumer_tools import dollars_to_cents\n\n"
        "def test_conversion():\n"
        "    assert dollars_to_cents(100) == 10000\n"
        "    assert dollars_to_cents(0) == 0\n"
        "    assert dollars_to_cents(12.34) == 1234\n",
        encoding="utf-8",
    )
    criterion = test.read_bytes()
    generate_json(
        SuiteReport(
            name="Synthetic diagnostic evidence",
            timestamp="2026-01-01T00:00:00Z",
            duration_ms=1,
            tests=[
                CaseReport(
                    name="test_money.py::test_conversion",
                    outcome="failed",
                    duration_ms=1,
                    error="AssertionError: 10001 != 10000",
                    eval_name="money",
                    eval_result=EvalResult(
                        turns=[
                            Turn(
                                role="assistant",
                                content="",
                                tool_calls=[
                                    ToolCall(
                                        name="dollars_to_cents",
                                        arguments={"amount": 100},
                                        result="10001",
                                        call_id="synthetic-call",
                                        completion_received=True,
                                        success=True,
                                    )
                                ],
                            )
                        ],
                        success=True,
                        evidence_complete=True,
                    ),
                )
            ],
            failed=1,
        ),
        tmp_path / "evidence.json",
    )
    result = await copilot_eval(
        CopilotEval(
            name="companion-investigation",
            model=DEFAULT_MODEL,
            working_directory=str(tmp_path),
            skill_directories=[str(SKILL)],
            instructions="Use the pytest-skill-engineering skill to investigate source and evidence.",
        ),
        "Inspect evidence.json, consumer_tools.py and test_money.py. Explain the supported "
        "cause and fix only consumer_tools.py. Do not change tests, evidence, or output criteria. "
        "Do not start Copilot sessions, install packages or run any paid tests.",
    )
    assert result.success, result.error
    assert test.read_bytes() == criterion
    checked = _pytest(tmp_path, str(test))
    record_property(
        "source_verification",
        {"exit_code": checked.returncode, "criteria_unchanged": test.read_bytes() == criterion},
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
