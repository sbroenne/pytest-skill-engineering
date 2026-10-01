"""Isolated skill comparisons with fixed numerical checks on both sides."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from pytest_skill_engineering.copilot import CopilotEval

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot, pytest.mark.skill]
SKILL = Path(__file__).parent.parent / "skills" / "math-helper"


async def test_skill_comparison_preserves_isolation_and_side_verification(
    ab_run,
    record_property,
):
    baseline = CopilotEval(
        name="math-baseline",
        model=DEFAULT_MODEL,
        instructions="Use Python arithmetic and save only the requested JSON artifact.",
    )
    treatment = replace(baseline, name="math-with-skill", skill_directories=[str(SKILL)])
    before, after = await ab_run(
        baseline,
        treatment,
        "Compute the final amounts for compound interest with annual compounding. "
        "Use principal=1000, rate=0.05, years=3 and principal=250, rate=0.10, years=2. "
        "Write amounts.json containing a JSON list of those two amounts, without currency rounding.",
    )
    assert before.agent is not None and after.agent is not None
    assert before.agent.working_directory != after.agent.working_directory
    checks = []
    for side, result in (("baseline", before), ("treatment", after)):
        assert result.agent is not None and result.agent.working_directory is not None
        output = Path(result.agent.working_directory) / "amounts.json"
        observed = json.loads(output.read_text(encoding="utf-8"))
        verified = observed == pytest.approx([1000 * 1.05**3, 250 * 1.10**2], abs=0.00001)
        record_property(
            f"{side}_verification",
            {"artifact": str(output), "observed": observed, "passed": verified},
        )
        checks.append(result.success and verified)
    assert all(checks), "Both sides must meet the same numerical criterion."
