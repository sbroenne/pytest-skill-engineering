"""Explicitly invoked real-Copilot comparisons; not part of default collection."""

from __future__ import annotations

from pathlib import Path

import pytest
from skill_dogfood.workflow import run_workflow

pytestmark = [pytest.mark.copilot, pytest.mark.skill]


@pytest.mark.parametrize("variant", ["without-skill", "with-skill"])
async def test_write_run_fix_rerun(copilot_eval, tmp_path, record_property, variant):
    await run_workflow(
        copilot_eval=copilot_eval,
        record_property=record_property,
        root=Path(__file__).resolve().parents[4],
        workspace=tmp_path,
        variant=variant,
    )
