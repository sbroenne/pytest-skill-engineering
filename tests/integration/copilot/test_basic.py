"""Basic Copilot tool usage tests.

Parametrized across models to compare behavior.
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

from .conftest import MODELS


@pytest.mark.copilot
class TestFileOperations:
    """Test file creation and code quality across models."""

    @pytest.mark.parametrize("model", MODELS)
    async def test_create_module_with_tests(self, copilot_eval, tmp_path, model):
        """Eval creates a module and its test file with working code."""
        agent = CopilotEval(
            name=f"coder-{model}",
            model=model,
            instructions="You are a Python developer. Create production-quality code.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a Python module called calculator.py with functions add, subtract, "
            "multiply, and divide. The divide function should raise ValueError on "
            "division by zero. Do NOT run or test the code, just create the file.",
        )
        assert result.success, f"{model} failed: {result.error}"

        # File exists
        assert (tmp_path / "calculator.py").exists(), f"{model}: calculator.py missing"

        # Module has all four functions
        calc = (tmp_path / "calculator.py").read_text()
        for fn in ("def add", "def subtract", "def multiply", "def divide"):
            assert fn in calc, f"{model}: {fn} not found in calculator.py"

        # Error handling present
        assert "ValueError" in calc or "ZeroDivisionError" in calc, (
            f"{model}: no error handling in divide"
        )

        # Eval used tools
        assert len(result.all_tool_calls) > 0, f"{model}: no tool calls"

    @pytest.mark.parametrize("model", MODELS)
    async def test_refactor_existing_code(self, copilot_eval, tmp_path, model):
        """Eval reads existing code and refactors it."""
        # Seed a file with intentionally messy code
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
            name=f"refactorer-{model}",
            model=model,
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
        assert result.success, f"{model} failed: {result.error}"

        refactored = messy.read_text()
        # The agent should have added documentation — type hints and/or a docstring.
        # Renaming is optional (a backward-compat alias is a valid refactoring choice).
        has_documentation = (
            '"""' in refactored
            or "->" in refactored
            or ": int" in refactored
            or ": float" in refactored
        )
        assert has_documentation, (
            f"{model}: no type hints or docstring added during refactor.\n"
            f"Refactored content:\n{refactored}"
        )
