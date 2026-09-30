"""Consumer-owned verification of a real plugin skill using the normal eval fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_skill_engineering.copilot import CopilotEval

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot, pytest.mark.skill]
PLUGIN_DIR = Path(__file__).parents[1] / "plugins" / "banking-plugin"
SKILL_DIR = PLUGIN_DIR / "skills" / "financial-literacy"


async def test_plugin_skill_workflow_has_concrete_arithmetic_verification(
    copilot_eval,
    tmp_path,
    record_property,
):
    agent = CopilotEval(
        name="plugin-financial-literacy",
        model=DEFAULT_MODEL,
        instructions="Apply the financial-literacy skill. Save the requested JSON artifact.",
        working_directory=str(tmp_path),
        skill_directories=[str(SKILL_DIR)],
    )
    result = await copilot_eval(
        agent,
        "Starting balances are checking=1500 and savings=3000. A transfer of 100 from "
        "checking to savings has no fees. Calculate the new balances and write balances.json "
        "with exactly the numeric fields checking, savings and total. Do not contact a real bank.",
    )
    assert result.success, result.error
    observed = json.loads((tmp_path / "balances.json").read_text(encoding="utf-8"))
    expected = {"checking": 1400, "savings": 3100, "total": 4500}
    record_property(
        "verification",
        {
            "artifact": "balances.json",
            "observed": observed,
            "expected": expected,
            "passed": observed == expected,
        },
    )
    assert observed == expected
