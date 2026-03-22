"""Level 17 — End-to-end skill-creator workflow against a real plugin.

Runs ALL 4 phases of the Anthropic skill-creator workflow against the
banking-plugin's financial-literacy skill:
  Phase 1: Author — load and validate SKILL.md
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

from pytest_skill_engineering.core.skill import Skill
from pytest_skill_engineering.core.skill_evals import has_skill_evals, load_skill_evals

pytestmark = [pytest.mark.copilot]

PLUGIN_DIR = Path(__file__).parents[1] / "plugins" / "banking-plugin"
SKILL_DIR = PLUGIN_DIR / "skills" / "financial-literacy"


class TestPhase1Author:
    """Phase 1: Author — validate the skill loads correctly."""

    def test_skill_loads_from_plugin(self):
        """SKILL.md in plugin directory loads with valid metadata."""
        skill = Skill.from_path(SKILL_DIR)
        assert skill.metadata.name == "financial-literacy"
        assert skill.metadata.description == "Domain knowledge for banking operations"
        assert "banking" in skill.metadata.tags

    def test_skill_has_evals(self):
        """Plugin skill has evals/evals.json for automated testing."""
        assert has_skill_evals(SKILL_DIR)

    def test_evals_load_correctly(self):
        """Eval cases parse with correct structure."""
        cases = load_skill_evals(SKILL_DIR)
        assert len(cases) == 2
        assert cases[0].prompt
        assert len(cases[0].expectations) == 3
        assert len(cases[1].expectations) == 2


class TestPhase2Evaluate:
    """Phase 2: Evaluate — run evals via skill_eval_runner."""

    async def test_run_plugin_skill_evals(self, skill_eval_runner):
        """skill_eval_runner executes all evals against the plugin skill."""
        result = await skill_eval_runner(SKILL_DIR)
        assert result.skill_name == "financial-literacy"
        assert len(result.cases) == 2
        assert result.grading["summary"]["total"] >= 2

    async def test_grading_export(self, skill_eval_runner, tmp_path):
        """Grading output is skill-creator compatible."""
        result = await skill_eval_runner(
            SKILL_DIR,
            export_grading_path=tmp_path / "grading.json",
        )
        grading_file = tmp_path / "grading.json"
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
        result = await skill_refiner(SKILL_DIR)
        assert result.skill_name == "financial-literacy"
        assert isinstance(result.summary, str)
        assert result.failures_analyzed >= 0


class TestPhase4Benchmark:
    """Phase 4: Benchmark — with_skill vs without_skill comparison."""

    async def test_benchmark_plugin_skill(self, skill_benchmark):
        """skill_benchmark compares with/without skill performance."""
        result = await skill_benchmark(SKILL_DIR)
        assert result.skill_name == "financial-literacy"
        assert len(result.cases) == 2
        assert 0.0 <= result.baseline_pass_rate <= 1.0
        assert 0.0 <= result.treatment_pass_rate <= 1.0
        assert isinstance(result.improvement, float)

    async def test_benchmark_summary(self, skill_benchmark):
        """Benchmark produces human-readable summary."""
        result = await skill_benchmark(SKILL_DIR)
        summary = result.summary()
        assert "financial-literacy" in summary
