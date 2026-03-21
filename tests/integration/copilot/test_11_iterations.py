"""Level 11 — Iterations: run each test N times for reliability measurement.

Uses the --aitest-iterations=N CLI flag to run each test multiple times.
The report aggregates iterations per test and shows iteration pass rate,
enabling flakiness detection and reliability baselines.

Mirrors pydantic/test_11_iterations.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_11_iterations.py -v --aitest-iterations=3
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]


class TestIterationBaseline:
    """Run Copilot tests multiple times to establish reliability baselines.

    When invoked with ``--aitest-iterations=3``, each test runs 3 times.
    The report aggregates iterations per test and shows an iteration pass rate.
    """

    async def test_file_creation_reliability(self, copilot_eval, tmp_path):
        """Create a single file — should be 100% reliable."""
        agent = CopilotEval(
            name="reliable-creator",
            instructions="Create Python files as requested. Be precise and concise.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create hello.py with a main() function that prints 'hello'.",
        )
        assert result.success, f"File creation failed: {result.error}"
        assert (tmp_path / "hello.py").exists(), "hello.py was not created"

        content = (tmp_path / "hello.py").read_text()
        assert "def main" in content, "main() function not found in hello.py"

    async def test_refactor_reliability(self, copilot_eval, tmp_path):
        """Refactor existing code — may show flakiness across iterations."""
        original = tmp_path / "messy.py"
        original.write_text(
            "def f(x,y):\n"
            "    r = x + y\n"
            "    if r > 0:\n"
            "        return True\n"
            "    else:\n"
            "        return False\n"
        )

        agent = CopilotEval(
            name="reliable-refactorer",
            instructions=(
                "Refactor code for clarity: use descriptive names, add type hints, simplify logic."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Read messy.py and refactor it for clarity. Save the improved version.",
        )
        assert result.success, f"Refactor failed: {result.error}"

        refactored = original.read_text()
        assert refactored != (
            "def f(x,y):\n"
            "    r = x + y\n"
            "    if r > 0:\n"
            "        return True\n"
            "    else:\n"
            "        return False\n"
        ), "File was not modified — refactor had no effect"

    async def test_multi_file_reliability(self, copilot_eval, tmp_path):
        """Create multiple related files — checks stability of complex operations."""
        agent = CopilotEval(
            name="reliable-multi",
            instructions=(
                "Create Python files as requested. Create all files specified. Be precise."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create two files: 1) math_ops.py with add(a, b) and subtract(a, b) "
            "functions, and 2) test_math_ops.py with pytest tests for both functions.",
        )
        assert result.success, f"Multi-file creation failed: {result.error}"

        py_files = list(tmp_path.rglob("*.py"))
        assert len(py_files) >= 2, (
            f"Expected at least 2 Python files, got {len(py_files)}: {[f.name for f in py_files]}"
        )
