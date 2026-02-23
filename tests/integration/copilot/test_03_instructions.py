"""Level 03 — Instructions: prove different instructions produce different outputs.

Tests that CopilotEval instructions measurably change behavior:
verbose vs concise documentation, framework steering, defensive coding.
Also tests excluded_tools for tool restriction.

Mirrors pydantic/test_03_prompts.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_03_instructions.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]


class TestInstructionsDifferentiate:
    """Different instructions produce measurably different outputs."""

    async def test_verbose_instructions_produce_documented_code(self, copilot_eval, tmp_path):
        """Instructions requiring docstrings produce documented code."""
        agent = CopilotEval(
            name="documented-coder",
            instructions=(
                "You write fully documented Python. EVERY function MUST have:\n"
                '- A docstring: """What this function does."""\n'
                "- Type hints on all parameters and the return value.\n"
                "No exceptions to these rules."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create calculator.py with add(a, b), subtract(a, b), multiply(a, b), divide(a, b).",
        )
        assert result.success
        content = (tmp_path / "calculator.py").read_text()
        assert '"""' in content or "'''" in content, (
            "Verbose instructions required docstrings — none found."
        )
        assert "->" in content, "Verbose instructions required return type hints — none found."

    async def test_concise_instructions_suppress_documentation(self, copilot_eval, tmp_path):
        """Instructions forbidding documentation produce minimal code."""
        agent = CopilotEval(
            name="minimal-coder",
            instructions=(
                "Write minimal Python code only. "
                "NO docstrings whatsoever. NO type hints. NO comments of any kind. "
                "Pure function definitions and logic only. Violating this is an error."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create calculator.py with add(a, b), subtract(a, b), multiply(a, b), divide(a, b).",
        )
        assert result.success
        content = (tmp_path / "calculator.py").read_text()
        assert '"""' not in content and "'''" not in content, (
            "Concise instructions forbade docstrings — but they appeared."
        )

    async def test_framework_instruction_steers_library_choice(self, copilot_eval, tmp_path):
        """Instructions specifying FastAPI result in FastAPI being used."""
        agent = CopilotEval(
            name="fastapi-dev",
            instructions=(
                "You are a FastAPI specialist. ALWAYS use FastAPI for web APIs. "
                "Never use Flask, Bottle, Starlette directly, or the standard library."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            'Create a web API with a GET /health endpoint that returns {"status": "ok"}.',
        )
        assert result.success
        py_files = list(tmp_path.rglob("*.py"))
        assert len(py_files) > 0, "No Python files created"
        all_code = "\n".join(f.read_text() for f in py_files)
        assert "fastapi" in all_code.lower(), (
            "Framework-specific instructions should have used FastAPI.\n"
            f"Files created: {[f.name for f in py_files]}"
        )

    async def test_error_handling_instruction_produces_defensive_code(self, copilot_eval, tmp_path):
        """Instructions requiring defensive coding produce try/except blocks."""
        agent = CopilotEval(
            name="defensive-coder",
            instructions=(
                "Always write production-ready, defensive Python code. "
                "All I/O operations MUST use try/except to handle failures explicitly. "
                "Never let exceptions propagate uncaught from I/O functions."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create file_reader.py with a read_json(path) function that "
            "reads and returns parsed JSON.",
        )
        assert result.success
        content = (tmp_path / "file_reader.py").read_text()
        assert "try" in content and "except" in content, (
            "Error handling instructions required try/except — not found."
        )


class TestToolRestrictions:
    """excluded_tools prevents the eval from calling blocked tools."""

    async def test_excluded_tool_is_never_called(self, copilot_eval, tmp_path):
        """Eval with run_in_terminal excluded never calls that tool."""
        agent = CopilotEval(
            name="no-terminal",
            instructions="Create files as requested. Do not run any terminal commands.",
            working_directory=str(tmp_path),
            excluded_tools=["run_in_terminal"],
        )
        result = await copilot_eval(agent, "Create safe.py with print('safe')")
        assert result.success
        assert not result.tool_was_called("run_in_terminal"), (
            f"Excluded tool 'run_in_terminal' was called. "
            f"All tools used: {result.tool_names_called}"
        )
