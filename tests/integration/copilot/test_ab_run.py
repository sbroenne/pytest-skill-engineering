"""Integration tests for the ab_run fixture.

Proves that ab_run correctly:
- Creates isolated directories for each agent
- Runs both agents against the same task
- Returns a (baseline, treatment) tuple of real CopilotResult objects
- The agents do NOT share workspace (files from one don't appear in the other)

These tests require GitHub Copilot credentials.
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.agent import CopilotAgent


@pytest.mark.copilot
class TestAbRunFixture:
    """Integration tests for the ab_run fixture."""

    async def test_ab_run_returns_two_results(self, ab_run):
        """ab_run returns a tuple of two successful CopilotResults."""
        from pytest_skill_engineering.copilot.result import CopilotResult

        baseline = CopilotAgent(
            name="baseline",
            instructions="Create files as requested.",
        )
        treatment = CopilotAgent(
            name="treatment",
            instructions="Create files as requested.",
        )

        b, t = await ab_run(baseline, treatment, "Create hello.txt with the text 'hello'.")

        assert isinstance(b, CopilotResult)
        assert isinstance(t, CopilotResult)
        assert b.success, f"Baseline failed: {b.error}"
        assert t.success, f"Treatment failed: {t.error}"

    async def test_ab_run_isolates_working_directories(self, ab_run, tmp_path):
        """Files created by baseline agent do not appear in treatment workspace."""
        baseline = CopilotAgent(
            name="baseline",
            instructions="Create files as requested.",
        )
        treatment = CopilotAgent(
            name="treatment",
            instructions="Create files as requested.",
        )

        task = "Create a file called sentinel.txt containing the text 'hello'."
        b, t = await ab_run(baseline, treatment, task)

        assert b.success and t.success

        baseline_dir = tmp_path / "baseline"
        treatment_dir = tmp_path / "treatment"

        # Both dirs must exist (created by ab_run)
        assert baseline_dir.exists(), "ab_run did not create baseline/ dir"
        assert treatment_dir.exists(), "ab_run did not create treatment/ dir"

        # Dirs must be DIFFERENT (not the same path)
        assert baseline_dir != treatment_dir

    async def test_ab_run_produces_differential_output(self, ab_run):
        """Treatment instruction change produces measurably different output.

        Baseline: no special instructions (no docstrings expected).
        Treatment: explicit docstring mandate.

        This is the canonical A/B test — proves the fixture enables real
        differential testing, not just running the same thing twice.
        """
        baseline = CopilotAgent(
            name="baseline",
            instructions=(
                "Write minimal Python code only. "
                "NO docstrings whatsoever. NO type hints. NO comments. "
                "Pure function definitions and logic only."
            ),
        )
        treatment = CopilotAgent(
            name="treatment",
            instructions=(
                "Write fully documented Python. EVERY function MUST have:\n"
                '- A docstring: """What this function does."""\n'
                "- Type hints on all parameters and return value."
            ),
        )

        b, t = await ab_run(
            baseline,
            treatment,
            "Create calculator.py with add(a, b) and subtract(a, b).",
        )

        assert b.success, f"Baseline failed: {b.error}"
        assert t.success, f"Treatment failed: {t.error}"

        # Verify isolation: each result knows its own working directory
        assert b.working_directory != t.working_directory, (
            "Baseline and treatment should have different working directories"
        )

        # Verify differential output
        baseline_code = b.file("calculator.py")
        treatment_code = t.file("calculator.py")

        # Treatment should have docstrings; baseline should not
        assert '"""' in treatment_code or "'''" in treatment_code, (
            "Treatment instruction required docstrings but none found.\n"
            f"Treatment code:\n{treatment_code}"
        )
        assert '"""' not in baseline_code and "'''" not in baseline_code, (
            "Baseline instruction forbade docstrings but they appeared.\n"
            f"Baseline code:\n{baseline_code}"
        )

    async def test_ab_run_working_directories_are_accessible_via_result(self, ab_run, tmp_path):
        """CopilotResult.working_directory points to the correct isolated dir."""
        baseline = CopilotAgent(name="baseline", instructions="Create files as requested.")
        treatment = CopilotAgent(name="treatment", instructions="Create files as requested.")

        b, t = await ab_run(
            baseline,
            treatment,
            "Create a file called check.txt with content 'check'.",
        )

        assert b.success and t.success

        # working_directory on result should point to the isolated dirs
        assert b.working_directory == tmp_path / "baseline"
        assert t.working_directory == tmp_path / "treatment"
