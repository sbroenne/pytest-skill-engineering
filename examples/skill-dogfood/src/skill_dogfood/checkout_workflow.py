"""A repeated, fixed-criteria experiment using only native framework execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from pytest_skill_engineering.reporting import load_suite_report
from skill_dogfood.checkout import criteria_digest, inspect_checkout, seed_checkout, workflow_checks
from skill_dogfood.consumer import MODEL
from skill_dogfood.workflow import (
    EvalRun,
    RecordProperty,
    Variant,
    prepare_historical_skill,
    project_tools,
    run_consumer,
    validate_authored_test,
    workflow_eval,
)

SYSTEM_PROMPT = (
    "Work on the customer's checkout project using the supplied project tools. "
    "Read the project requirements, API documentation, and available guidance. "
    "Write only the file authorized for the task. Do not execute commands, "
    "install packages, or create another model runner."
)
AUTHOR_TASK = (
    "Write test_checkout.py to test this imported-order checkout workflow using "
    "pytest-skill-engineering and the supplied fixtures. Check the customer's "
    "requirements and record your observations. Author the test only; the customer runs it."
)
REPAIR_TASK = (
    "The customer ran your test. Investigate before.json alongside the source and "
    "requirements, then repair checkout_cli.py so the checkout workflow is correct. "
    "Do not change the authored test, inputs, configuration, or saved evidence. "
    "Do not run paid tests yourself."
)
API = """# Consumer API

Request these separate pytest fixtures as test parameters:
- checkout_eval: the preconfigured CopilotEval for the project's checkout tool.
- checkout_task: the user's request to run the supplied imported-order workflow.
- copilot_eval: async framework execution; await copilot_eval(checkout_eval, checkout_task).
- checkout_observation: a no-argument callable returning the actual workflow data
  after execution. Keys: preview, post, repeat, conflict, second, read.
- checkout_inputs: dictionary keyed by order.csv, other.csv, and conflict.csv.
  Each value contains csv_text (exact UTF-8 text) and fingerprint (SHA-256 of
  actual bytes). Use these supplied input values instead of opening files.
- record_property: pytest's function for recording JSON-compatible observations.

Each observation contains exit_code, output (parsed command stdout), stderr, and
disk (parsed actual ledger file, or None when it does not exist). SDK session
completion is in result.success; result.evidence_complete describes capture.
The checkout tool runs all six CLI operations from the README, exactly once.
One async test function and one copilot_eval execution are permitted.
Plain assertion helpers are allowed, but no extra test cases or fixture overrides.
Allowed imports are __future__.annotations, decimal, hashlib, json, pytest, and
CopilotEval/CopilotResult from pytest_skill_engineering.copilot.
Do not use pathlib, direct file I/O, subprocesses, dynamic imports, skips, xfail,
or parametrization in the generated test. All application access is via fixtures.
"""


def check_checkout_consumer(
    project: Path, evidence: Path, exit_code: int, *, repaired: bool
) -> None:
    suite = load_suite_report(evidence)
    assert len(suite.tests) == 1, "Require one actual consumer execution"
    case = suite.tests[0]
    assert case.eval_result is not None
    result = case.eval_result
    assert result.success and result.evidence_complete, result.error
    assert result.configuration["model"] == MODEL
    calls = [call for turn in result.turns for call in turn.tool_calls]
    assert len(calls) == 1 and calls[0].name == "checkout"
    assert calls[0].arguments == {"order_file": "order.csv", "request_id": "checkout-1"}
    assert calls[0].success and calls[0].evidence_complete
    observations = [value for name, value in case.properties if name == "actual_checkout"]
    assert len(observations) == 1
    checks = workflow_checks(observations[0], project)
    if repaired:
        assert all(check["passed"] for check in checks), checks
        assert exit_code == 0 and case.outcome == "passed"
    else:
        assert observations[0]["post"]["output"]["total_cents"] == 35
        assert observations[0]["post"]["disk"]["postings"][0]["total_cents"] == 0
        assert not all(check["passed"] for check in checks)
        assert exit_code == 1 and case.outcome == "failed"
        assert case.error and "AssertionError" in case.error


async def run_checkout_workflow(
    *,
    copilot_eval: EvalRun,
    record_property: RecordProperty,
    root: Path,
    workspace: Path,
    variant: Variant,
    trial: int,
) -> None:
    project = workspace / "consumer"
    seed_checkout(project)
    (project / "API.md").write_text(API, encoding="utf-8")
    (project / "conftest.py").write_text(
        'pytest_plugins = ["skill_dogfood.checkout_consumer"]\n',
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nasyncio_mode = "auto"\n',
        encoding="utf-8",
    )
    protected = {
        name: (project / name).read_bytes()
        for name in (
            "README.md",
            "API.md",
            "conftest.py",
            "pyproject.toml",
            "order.csv",
            "other.csv",
            "conflict.csv",
        )
    }
    application = project / "checkout_cli.py"
    starting = application.read_bytes()
    skill = prepare_historical_skill(root, workspace)
    evidence_dir = root / "aitest-reports" / "skill-dogfood" / "checkout" / variant / uuid4().hex
    evidence_dir.mkdir(parents=True)
    milestones: list[str] = []
    record_property("scenario", "checkout")
    record_property("comparison_variant", variant)
    record_property("trial", trial)
    criteria = criteria_digest()
    record_property("criteria_sha256", criteria)
    protocol = (
        SYSTEM_PROMPT,
        AUTHOR_TASK,
        REPAIR_TASK,
        API,
        MODEL,
        180,
        24,
        120,
        4,
        Path(__file__).with_name("workflow.py").read_text(encoding="utf-8"),
    )
    record_property(
        "protocol_sha256",
        hashlib.sha256(json.dumps(protocol).encode()).hexdigest(),
    )
    record_property("skill_sha256", hashlib.sha256((skill / "SKILL.md").read_bytes()).hexdigest())
    record_property("environment", {"python": sys.version, "sdk": version("github-copilot-sdk")})
    record_property("evidence_directory", str(evidence_dir))
    record_property("workflow_milestones", milestones)
    readable = {name: project / name for name in (*protected, "checkout_cli.py")}
    if variant == "with-skill":
        readable.update(
            {
                "SKILL.md": skill / "SKILL.md",
                "test-patterns.md": skill / "references" / "test-patterns.md",
                "investigation.md": skill / "references" / "investigation.md",
            }
        )
    test = project / "test_checkout.py"

    def intact() -> None:
        assert all((project / name).read_bytes() == data for name, data in protected.items())
        assert criteria_digest() == criteria

    author_reads: list[str] = []
    tools = project_tools(readable, {"test_checkout.py": test}, author_reads)
    agent = workflow_eval(
        variant,
        "author",
        project,
        skill,
        tools,
        system_prompt=SYSTEM_PROMPT,
        name_prefix=f"checkout-trial-{trial}",
    )
    result = await copilot_eval(agent, AUTHOR_TASK)
    record_property("author_guidance_reads", author_reads)
    assert result.success and result.evidence_complete, result.error
    milestones.append("author-session-completed")
    assert application.read_bytes() == starting
    intact()
    if variant == "with-skill":
        assert "SKILL.md" in author_reads
    validate_authored_test(test)
    unchanged = test.read_bytes()
    milestones.append("authored-test-contract-valid")
    before = evidence_dir / "before.json"
    run = await asyncio.to_thread(run_consumer, project, before, "test_checkout.py")
    record_property(
        "before_consumer",
        {
            "exit_code": run.returncode,
            "evidence": str(before),
            "stdout": run.stdout,
            "stderr": run.stderr,
        },
    )
    assert before.is_file(), run.stdout + run.stderr
    check_checkout_consumer(project, before, run.returncode, repaired=False)
    milestones.append("real-before-business-failure")
    before_bytes = before.read_bytes()
    assert application.read_bytes() == starting and test.read_bytes() == unchanged
    intact()
    readable.update({"test_checkout.py": test, "before.json": before})
    repair_reads: list[str] = []
    tools = project_tools(readable, {"checkout_cli.py": application}, repair_reads)
    agent = workflow_eval(
        variant,
        "repair",
        project,
        skill,
        tools,
        system_prompt=SYSTEM_PROMPT,
        name_prefix=f"checkout-trial-{trial}",
    )
    result = await copilot_eval(agent, REPAIR_TASK)
    record_property("repair_guidance_reads", repair_reads)
    assert result.success and result.evidence_complete, result.error
    milestones.append("repair-session-completed")
    assert "before.json" in repair_reads
    if variant == "with-skill":
        assert "SKILL.md" in repair_reads
    assert test.read_bytes() == unchanged and before.read_bytes() == before_bytes
    intact()
    observed = await asyncio.to_thread(inspect_checkout, project)
    record_property("independent_cli_verification", observed)
    assert all(check["passed"] for check in observed), observed
    milestones.append("independent-checks-passed")
    after = evidence_dir / "after.json"
    run = await asyncio.to_thread(run_consumer, project, after, "test_checkout.py")
    record_property(
        "after_consumer",
        {
            "exit_code": run.returncode,
            "evidence": str(after),
            "stdout": run.stdout,
            "stderr": run.stderr,
        },
    )
    assert after.is_file(), run.stdout + run.stderr
    check_checkout_consumer(project, after, run.returncode, repaired=True)
    assert test.read_bytes() == unchanged and before.read_bytes() == before_bytes
    intact()
    milestones.append("unchanged-after-test-passed")
