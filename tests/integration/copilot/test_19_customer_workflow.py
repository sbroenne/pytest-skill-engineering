"""Run the ordinary customer workflow without a framework companion skill."""

from __future__ import annotations

from pathlib import Path

import pytest
from skill_dogfood.workflow import run_workflow

pytestmark = pytest.mark.copilot


async def test_customer_workflow(copilot_eval, tmp_path, record_property):
    await run_workflow(
        copilot_eval=copilot_eval,
        record_property=record_property,
        root=Path(__file__).resolve().parents[3],
        workspace=tmp_path,
        variant="without-skill",
    )
