"""Level 17 — End-to-end skill-creator workflow against a real plugin.

Runs the expensive phases of the Anthropic skill-creator workflow against the
banking-plugin's financial-literacy skill:
  Phase 2: Evaluate — run evals.json via skill_eval_runner
  Phase 3: Refine — analyze failures and suggest improvements
  Phase 4: Benchmark — compare with_skill vs without_skill

This is the integration test that proves the full pipeline works
against a real plugin, not just isolated skill directories.

Run with: pytest tests/integration/copilot/test_17_plugin_skill_workflow.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot]

PLUGIN_DIR = Path(__file__).parents[1] / "plugins" / "banking-plugin"
SKILL_DIR = PLUGIN_DIR / "skills" / "financial-literacy"


class TestPhase2Evaluate:
    """Phase 2: Evaluate — run evals via skill_eval_runner."""

    async def test_run_plugin_skill_evals_and_export(self, skill_eval_runner, tmp_path):
        """skill_eval_runner executes all evals once and exports grading."""
        grading_file = tmp_path / "grading.json"
        result = await skill_eval_runner(
            SKILL_DIR,
            model=DEFAULT_MODEL,
            export_grading_path=grading_file,
        )
        assert result.skill_name == "financial-literacy"
        assert len(result.cases) == 2
        assert result.grading["summary"]["total"] >= 2
        assert grading_file.exists()

        import json

        grading = json.loads(grading_file.read_text())
        assert "summary" in grading
        assert "expectations" in grading
        assert "execution_metrics" in grading


class TestPhase3Refine:
    """Phase 3: Refine — analyze failures and suggest improvements."""

    async def test_refiner_analyzes_plugin_skill(self, skill_refiner):
        """skill_refiner produces analysis for the plugin skill."""
        result = await skill_refiner(SKILL_DIR, model=DEFAULT_MODEL)
        assert result.skill_name == "financial-literacy"
        assert isinstance(result.summary, str)
        assert result.failures_analyzed >= 0


class TestPhase4Benchmark:
    """Phase 4: Benchmark — with_skill vs without_skill comparison."""

    async def test_benchmark_plugin_skill_summary(self, skill_benchmark):
        """skill_benchmark compares with/without skill performance once."""
        result = await skill_benchmark(SKILL_DIR, model=DEFAULT_MODEL)
        assert result.skill_name == "financial-literacy"
        assert len(result.cases) == 2
        assert 0.0 <= result.baseline_pass_rate <= 1.0
        assert 0.0 <= result.treatment_pass_rate <= 1.0
        assert isinstance(result.improvement, float)
        summary = result.summary()
        assert "financial-literacy" in summary
