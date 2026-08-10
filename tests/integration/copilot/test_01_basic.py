"""Level 01 — Basic Copilot file operations: create and refactor code.

Tests that the Copilot coding agent can create production-quality Python
modules and refactor existing code using the shared economical default model.

Mirrors pydantic/test_01_basic.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_01_basic.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

from .conftest import DEFAULT_MODEL

pytestmark = [pytest.mark.copilot]


class TestFileOperations:
    """Test file creation and code quality with the default integration model."""

    async def test_create_module_with_tests(self, copilot_eval, tmp_path):
        """Eval creates a module with working code and all required functions."""
        agent = CopilotEval(
            name=f"coder-{DEFAULT_MODEL}",
            model=DEFAULT_MODEL,
            instructions="You are a Python developer. Create production-quality code.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a Python module called calculator.py with functions add, subtract, "
            "multiply, and divide. The divide function should raise ValueError on "
            "division by zero. Do NOT run or test the code, just create the file.",
        )
        assert result.success, f"{DEFAULT_MODEL} failed: {result.error}"

        assert (tmp_path / "calculator.py").exists(), f"{DEFAULT_MODEL}: calculator.py missing"

        calc = (tmp_path / "calculator.py").read_text()
        for fn in ("def add", "def subtract", "def multiply", "def divide"):
            assert fn in calc, f"{DEFAULT_MODEL}: {fn} not found in calculator.py"

        assert "ValueError" in calc or "ZeroDivisionError" in calc, (
            f"{DEFAULT_MODEL}: no error handling in divide"
        )
        assert len(result.all_tool_calls) > 0, f"{DEFAULT_MODEL}: no tool calls"

    async def test_refactor_existing_code(self, copilot_eval, tmp_path):
        """Eval reads existing code and refactors it for clarity."""
        messy = tmp_path / "messy.py"
        messy.write_text(
            "def f(x,y,z):\n"
            "    result = x + y\n"
            "    result = result * z\n"
            "    if result > 100:\n"
            "        return True\n"
            "    else:\n"
            "        return False\n"
        )

        agent = CopilotEval(
            name=f"refactorer-{DEFAULT_MODEL}",
            model=DEFAULT_MODEL,
            instructions=(
                "You are a code reviewer. Refactor code for clarity: "
                "use descriptive names, simplify logic, add type hints and a docstring."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Read messy.py, refactor it for clarity, and save the improved version.",
        )
        assert result.success, f"{DEFAULT_MODEL} failed: {result.error}"

        refactored = messy.read_text()
        has_documentation = (
            '"""' in refactored
            or "->" in refactored
            or ": int" in refactored
            or ": float" in refactored
        )
        assert has_documentation, (
            f"{DEFAULT_MODEL}: no type hints or docstring added during refactor.\n"
            f"Refactored content:\n{refactored}"
        )
