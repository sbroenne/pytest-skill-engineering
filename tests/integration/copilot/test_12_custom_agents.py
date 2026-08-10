"""Level 12 — Custom agents: test custom agent dispatch and subagent routing.

Tests that CopilotEval custom agents produce expected outcomes (file creation)
and that forced subagent dispatch works when write tools are excluded.

Copilot-exclusive — no pydantic mirror (custom agents are a Copilot SDK feature).

Run with: pytest tests/integration/copilot/test_12_custom_agents.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]
CUSTOM_AGENT_MODEL = "gpt-5.5"
FORCED_SUBAGENT_MODEL = "gpt-5.4-mini"
_NATIVE_SUBAGENT_TOOLS = ["task"]

# Tools that let the orchestrator write files directly.
# Excluding these forces the orchestrator to delegate.
_WRITE_TOOLS = [
    "create_file",
    "replace_string_in_file",
    "multi_replace_string_in_file",
    "insert_edit_into_file",
    "run_in_terminal",
    "create_directory",
]


# =============================================================================
# Custom Agent Outcomes
# =============================================================================


class TestCustomAgentOutcomes:
    """Custom agents produce their expected file-based outcomes."""

    async def test_test_writer_agent_creates_test_file(self, copilot_eval, tmp_path):
        """Custom test-writer agent produces a pytest test file alongside code."""
        agent = CopilotEval(
            name="with-test-writer",
            model=CUSTOM_AGENT_MODEL,
            instructions=(
                "You are a senior developer. When you create code, "
                "always delegate test writing to the test-writer agent."
            ),
            working_directory=str(tmp_path),
            timeout_s=600.0,
            excluded_tools=_NATIVE_SUBAGENT_TOOLS,
            custom_agents=[
                {
                    "name": "test-writer",
                    "prompt": (
                        "You are a test specialist. Write pytest unit tests "
                        "for the given code. Include happy path and edge cases. "
                        "Save tests to a test_*.py file."
                    ),
                    "description": "Writes pytest unit tests for Python code.",
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Create calculator.py with add, subtract, multiply, and divide functions "
            "(divide raises ValueError on division by zero). Then have tests written for it.",
        )
        assert result.success, f"Failed: {result.error}"
        assert list(tmp_path.rglob("calculator.py")), "calculator.py was not created"
        test_files = list(tmp_path.rglob("test_*.py"))
        assert len(test_files) > 0, (
            "No test_*.py file created — test-writer custom agent may not have been invoked"
        )

    async def test_docs_writer_agent_creates_readme(self, copilot_eval, tmp_path):
        """Custom docs-writer agent produces a README.md for the project."""
        agent = CopilotEval(
            name="with-docs-writer",
            model=CUSTOM_AGENT_MODEL,
            instructions=(
                "You are a project lead. Create the requested code, then "
                "delegate README documentation to the docs-writer agent. "
                "The docs-writer must save its output to README.md in the project root."
            ),
            working_directory=str(tmp_path),
            excluded_tools=_NATIVE_SUBAGENT_TOOLS,
            custom_agents=[
                {
                    "name": "docs-writer",
                    "prompt": (
                        "You write README.md documentation for Python projects. "
                        "Create a clear, concise README with a description, "
                        "installation instructions, and a usage example. "
                        "Save the documentation to README.md in the project root."
                    ),
                    "description": "Writes README.md project documentation.",
                    "tools": ["create_file", "read_file", "insert_edit_into_file"],
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Create greeting.py with a greet(name: str) -> str function that returns "
            "'Hello, {name}!', then have documentation written for the project.",
        )
        assert result.success, f"Failed: {result.error}"
        assert any(inv.name == "docs-writer" for inv in result.subagent_invocations), (
            "docs-writer was not invoked"
        )
        assert (tmp_path / "greeting.py").exists(), "greeting.py was not created"
        assert (tmp_path / "README.md").exists(), (
            "README.md was not created — docs-writer agent may not have been invoked"
        )

    async def test_subagent_lifecycle_captured_when_invoked(self, copilot_eval, tmp_path):
        """When a custom agent is invoked, lifecycle events are captured correctly."""
        (tmp_path / "sort.py").write_text(
            "def bubble_sort(arr):\n"
            "    return sorted(arr)\n\n"
            "def quick_sort(arr):\n"
            "    return sorted(arr)\n",
            encoding="utf-8",
        )
        agent = CopilotEval(
            name="with-code-reviewer",
            model=CUSTOM_AGENT_MODEL,
            instructions=(
                "You manage a development team. For code-review requests, "
                "delegate the review to the code-reviewer before finishing."
            ),
            working_directory=str(tmp_path),
            excluded_tools=_NATIVE_SUBAGENT_TOOLS,
            custom_agents=[
                {
                    "name": "code-reviewer",
                    "prompt": (
                        "You review Python code for correctness and obvious edge cases. "
                        "Use read_file to inspect the requested file, then give a short "
                        "review and stop. Do not modify files or run shell commands."
                    ),
                    "description": "Reviews Python code quality and correctness.",
                    "tools": ["read_file"],
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Have the code-reviewer review sort.py and summarize whether the "
            "implementation looks correct.",
        )
        assert result.success, f"Failed: {result.error}"
        assert (tmp_path / "sort.py").exists(), "sort.py fixture was not created"

        for invocation in result.subagent_invocations:
            assert invocation.name, "SubagentInvocation.name must not be empty"
            assert invocation.status in ("selected", "started", "completed", "failed"), (
                f"Unexpected SubagentInvocation.status: {invocation.status!r}"
            )


# =============================================================================
# Forced Subagent Dispatch
# =============================================================================


class TestForcedSubagentDispatch:
    """When write tools are excluded, the orchestrator must delegate to a subagent."""

    async def test_subagent_invocations_non_empty(self, copilot_eval, tmp_path):
        """Orchestrator with excluded write tools dispatches to a subagent."""
        agent = CopilotEval(
            name="forced-orchestrator",
            model=FORCED_SUBAGENT_MODEL,
            instructions=(
                "You are an orchestrator. You MUST delegate all file creation "
                "to the file-writer agent via runSubagent. "
                "Do not attempt to create files yourself."
            ),
            working_directory=str(tmp_path),
            timeout_s=300.0,
            max_turns=20,
            excluded_tools=_WRITE_TOOLS + _NATIVE_SUBAGENT_TOOLS,
            custom_agents=[
                {
                    "name": "file-writer",
                    "prompt": (
                        "You create exactly one file per request. Use your available file "
                        "editing tools to write the requested file in the current working "
                        "directory, then stop. Do not inspect unrelated files or run shell "
                        "commands."
                    ),
                    "description": "Creates Python source files on disk.",
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Use the file-writer agent to create hello.py containing: print('hello world')",
        )
        assert result.success, f"Run failed: {result.error}"
        assert result.subagent_invocations, (
            "No subagent invocations recorded — orchestrator may have attempted "
            "to implement directly despite excluded write tools"
        )

    async def test_subagent_file_created(self, copilot_eval, tmp_path):
        """File created by subagent exists in the workspace."""
        agent = CopilotEval(
            name="forced-orchestrator-file",
            model=FORCED_SUBAGENT_MODEL,
            instructions=(
                "You are an orchestrator. Delegate all file creation to the "
                "file-writer agent via runSubagent."
            ),
            working_directory=str(tmp_path),
            timeout_s=300.0,
            max_turns=20,
            excluded_tools=_WRITE_TOOLS + _NATIVE_SUBAGENT_TOOLS,
            custom_agents=[
                {
                    "name": "file-writer",
                    "prompt": (
                        "You create exactly one file per request. Use your available file "
                        "editing tools to write the requested file in the current working "
                        "directory, then stop."
                    ),
                    "description": "Creates Python source files on disk.",
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Use the file-writer agent to create output.py containing: x = 42",
        )
        assert result.success, f"Run failed: {result.error}"
        assert list(tmp_path.rglob("output.py")), (
            "output.py not created — subagent did not write the file"
        )

    async def test_subagent_invocation_fields(self, copilot_eval, tmp_path):
        """SubagentInvocation objects have valid name and status fields."""
        agent = CopilotEval(
            name="forced-orchestrator-fields",
            model=FORCED_SUBAGENT_MODEL,
            instructions=(
                "You are an orchestrator. Delegate file creation to the "
                "file-writer agent via runSubagent."
            ),
            working_directory=str(tmp_path),
            timeout_s=300.0,
            max_turns=20,
            excluded_tools=_WRITE_TOOLS + _NATIVE_SUBAGENT_TOOLS,
            custom_agents=[
                {
                    "name": "file-writer",
                    "prompt": (
                        "You create exactly one file per request. Use your available file "
                        "editing tools to write the requested file in the current working "
                        "directory, then stop."
                    ),
                    "description": "Creates Python source files.",
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Use the file-writer agent to create result.py containing: done = True",
        )
        assert result.success, f"Run failed: {result.error}"
        assert result.subagent_invocations, "No subagent invocations recorded"

        for inv in result.subagent_invocations:
            assert inv.name, "SubagentInvocation.name must not be empty"
            assert inv.status in ("selected", "started", "completed", "failed"), (
                f"Unexpected SubagentInvocation.status: {inv.status!r}"
            )
