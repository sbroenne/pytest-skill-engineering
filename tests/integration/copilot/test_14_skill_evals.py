"""Loaded skill cases with explicit mathematical checks, not AI answer grading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_skill_engineering import export_grading, load_skill_evals
from pytest_skill_engineering.copilot import CopilotEval

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot, pytest.mark.skill]
SKILL = Path(__file__).parent.parent / "skills" / "math-helper"
CASES = load_skill_evals(SKILL)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
async def test_loaded_case_has_independently_checked_output(
    copilot_eval,
    tmp_path,
    record_property,
    case,
):
    """Verify declared numbers, not the original free-text expectation descriptions."""
    if case.id == 1:
        shape = (
            "Write answer.json with only a numeric 'final_amount' field, without currency rounding."
        )
        expectation = "Final amount equals 1000 * (1 + 0.05) ** 3."
    else:
        assert case.id == 2
        shape = "Write answer.json with only a 'coefficients' list, in descending power order."
        expectation = "Derivative coefficients equal [3, 4, -5]."
    agent = CopilotEval(
        name=f"loaded-math-case-{case.id}",
        model=DEFAULT_MODEL,
        working_directory=str(tmp_path),
        skill_directories=[str(SKILL)],
        instructions="Solve the requested calculation and save the requested JSON file.",
    )
    result = await copilot_eval(agent, f"{case.prompt}\n{shape}")
    assert result.success, result.error
    answer = json.loads((tmp_path / "answer.json").read_text(encoding="utf-8"))
    if case.id == 1:
        verified = answer["final_amount"] == pytest.approx(1000 * 1.05**3, abs=0.00001)
    else:
        verified = answer["coefficients"] == [3, 4, -5]
    record_property(
        "verification",
        {"case_id": case.id, "criterion": expectation, "observed": answer, "passed": verified},
    )
    grading = export_grading(result, [expectation], [verified], [json.dumps(answer)])
    (tmp_path / "grading.json").write_text(json.dumps(grading, indent=2), encoding="utf-8")
    assert grading["summary"]["total"] == 1
    assert grading["expectations"][0]["passed"] is verified
    assert verified, expectation
