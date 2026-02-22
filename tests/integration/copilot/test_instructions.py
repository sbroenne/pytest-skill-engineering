"""Instruction testing.

Proves that different CopilotAgent instructions produce measurably different
behaviors. Each test asserts a concrete, observable difference — not just
that the agent succeeded, but that the instruction actually changed the output.

Also contains the canonical test for excluded_tools (tool restriction behavior).
"""

from __future__ import annotations

import pytest

from pytest_aitest.copilot.agent import CopilotAgent


@pytest.mark.copilot
class TestInstructionsDifferentiate:
    """Different instructions produce measurably different outputs."""

    async def test_verbose_instructions_produce_documented_code(self, copilot_run, tmp_path):
        """Instructions explicitly requiring docstrings produce documented code.

        The instruction mandates docstrings AND type hints. Both must appear
        in the generated file — this is what proves the instruction was followed.
        """
        agent = CopilotAgent(
            name="documented-coder",
            instructions=(
                "You write fully documented Python. EVERY function MUST have:\n"
                '- A docstring: """What this function does."""\n'
                "- Type hints on all parameters and the return value.\n"
                "No exceptions to these rules."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create calculator.py with add(a, b), subtract(a, b), multiply(a, b), divide(a, b).",
        )
        assert result.success
        content = (tmp_path / "calculator.py").read_text()
        assert '"""' in content or "'''" in content, (
            "Verbose instructions required docstrings — none found in generated code."
        )
        assert "->" in content, (
            "Verbose instructions required return type hints — none found in generated code."
        )

    async def test_concise_instructions_suppress_documentation(self, copilot_run, tmp_path):
        """Instructions forbidding documentation produce minimal code.

        The instruction explicitly forbids docstrings, type hints, and comments.
        If the instruction is followed, none of those appear in the output.
        """
        agent = CopilotAgent(
            name="minimal-coder",
            instructions=(
                "Write minimal Python code only. "
                "NO docstrings whatsoever. NO type hints. NO comments of any kind. "
                "Pure function definitions and logic only. Violating this is an error."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create calculator.py with add(a, b), subtract(a, b), multiply(a, b), divide(a, b).",
        )
        assert result.success
        content = (tmp_path / "calculator.py").read_text()
        assert '"""' not in content and "'''" not in content, (
            "Concise instructions forbade docstrings — but they appeared in generated code."
        )

    async def test_framework_instruction_steers_library_choice(self, copilot_run, tmp_path):
        """Instructions specifying a framework result in that framework being used.

        The instruction mandates FastAPI. The generated code must import or
        reference FastAPI — not Flask, Django, or the stdlib http module.
        """
        agent = CopilotAgent(
            name="fastapi-dev",
            instructions=(
                "You are a FastAPI specialist. ALWAYS use FastAPI for web APIs. "
                "Never use Flask, Bottle, Starlette directly, or the standard library."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            'Create a web API with a GET /health endpoint that returns {"status": "ok"}.',
        )
        assert result.success
        py_files = list(tmp_path.rglob("*.py"))
        assert len(py_files) > 0, "No Python files created"
        all_code = "\n".join(f.read_text() for f in py_files)
        assert "fastapi" in all_code.lower(), (
            "Framework-specific instructions should have used FastAPI.\n"
            f"Files created: {[f.name for f in py_files]}\n"
            f"Code preview: {all_code[:500]}"
        )

    async def test_error_handling_instruction_produces_defensive_code(self, copilot_run, tmp_path):
        """Instructions requiring defensive coding produce try/except blocks.

        The instruction mandates try/except on all I/O. The generated code
        must have exception handling — this verifies the instruction changed the output.
        """
        agent = CopilotAgent(
            name="defensive-coder",
            instructions=(
                "Always write production-ready, defensive Python code. "
                "All I/O operations MUST use try/except to handle failures explicitly. "
                "Never let exceptions propagate uncaught from I/O functions."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create file_reader.py with a read_json(path) function that reads and returns parsed JSON.",
        )
        assert result.success
        content = (tmp_path / "file_reader.py").read_text()
        assert "try" in content and "except" in content, (
            "Error handling instructions required try/except — not found in generated code.\n"
            f"File content:\n{content}"
        )


@pytest.mark.copilot
class TestToolRestrictions:
    """excluded_tools configuration prevents the agent from calling blocked tools.

    This is the canonical test for tool restriction behavior. The same
    configuration is not tested in test_events.py or test_cli_tools.py.
    """

    async def test_excluded_tool_is_never_called(self, copilot_run, tmp_path):
        """Agent with run_in_terminal excluded never calls that tool."""
        agent = CopilotAgent(
            name="no-terminal",
            instructions="Create files as requested. Do not run any terminal commands.",
            working_directory=str(tmp_path),
            excluded_tools=["run_in_terminal"],
        )
        result = await copilot_run(agent, "Create safe.py with print('safe')")
        assert result.success
        assert not result.tool_was_called("run_in_terminal"), (
            f"Excluded tool 'run_in_terminal' was called. "
            f"All tools used: {result.tool_names_called}"
        )
