"""Repeated imported-order workflows with alternating comparison order."""

from __future__ import annotations

from pathlib import Path

import pytest
from skill_dogfood.checkout_workflow import run_checkout_workflow
from skill_dogfood.workflow import Variant

pytestmark = [pytest.mark.copilot, pytest.mark.skill]


@pytest.fixture
def variant(request: pytest.FixtureRequest, _aitest_iteration: int) -> Variant:
    order: tuple[Variant, Variant] = (
        ("without-skill", "with-skill")
        if _aitest_iteration % 2
        else ("with-skill", "without-skill")
    )
    return order[request.param]


@pytest.mark.parametrize("variant", [0, 1], indirect=True, ids=["first", "second"])
async def test_checkout_customer_workflow(
    copilot_eval, tmp_path, record_property, variant, _aitest_iteration
):
    await run_checkout_workflow(
        copilot_eval=copilot_eval,
        record_property=record_property,
        root=Path(__file__).resolve().parents[4],
        workspace=tmp_path,
        variant=variant,
        trial=_aitest_iteration,
    )
