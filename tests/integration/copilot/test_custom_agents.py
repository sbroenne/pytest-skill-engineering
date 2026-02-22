"""Custom agent routing tests.

Proves that custom agents (SDK ``CustomAgentConfig``) are configured and
produce their expected outputs. Tests assert on concrete file outcomes
rather than subagent invocation counts, since invocation is non-deterministic
(the LLM decides whether to route to a custom agent).

Custom agent fields:
    name        Unique agent name (required)
    prompt      The agent's instructions (required)
    description What the agent does — helps the model decide when to invoke it
    tools       Tools available to this agent (optional allowlist)
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval


@pytest.mark.copilot
class TestCustomAgentOutcomes:
    """Custom agents produce their expected file-based outcomes."""

    async def test_test_writer_agent_creates_test_file(self, copilot_eval, tmp_path):
        """Custom test-writer agent produces a pytest test file alongside code.

        The main agent is instructed to delegate test writing to the
        test-writer custom agent. We assert the test file is created —
        the observable proof that the custom agent did its job.
        """
        agent = CopilotEval(
            name="with-test-writer",
            instructions=(
                "You are a senior developer. When you create code, "
                "always delegate test writing to the test-writer agent."
            ),
            working_directory=str(tmp_path),
            timeout_s=600.0,
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
        """Custom docs-writer agent produces a README.md for the project.

        The docs-writer is tool-restricted to file operations only.
        We assert both the code file AND the README exist.
        """
        agent = CopilotEval(
            name="with-docs-writer",
            instructions=(
                "You are a project lead. Create the requested code, then "
                "delegate README documentation to the docs-writer agent."
            ),
            working_directory=str(tmp_path),
            custom_agents=[
                {
                    "name": "docs-writer",
                    "prompt": (
                        "You write README.md documentation for Python projects. "
                        "Create a clear, concise README with a description, "
                        "installation instructions, and a usage example."
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
        assert (tmp_path / "greeting.py").exists(), "greeting.py was not created"
        assert (tmp_path / "README.md").exists(), (
            "README.md was not created — docs-writer agent may not have been invoked"
        )

    async def test_subagent_lifecycle_captured_when_invoked(self, copilot_eval, tmp_path):
        """When a custom agent is invoked, its lifecycle events are captured correctly.

        Subagent invocation is non-deterministic — the model decides whether
        to route to the reviewer. If it does, the SubagentInvocation objects
        must have valid name and status fields.
        """
        agent = CopilotEval(
            name="with-code-reviewer",
            instructions=(
                "You manage a development team. After creating code, "
                "always ask the code-reviewer to check it before finishing."
            ),
            working_directory=str(tmp_path),
            custom_agents=[
                {
                    "name": "code-reviewer",
                    "prompt": (
                        "You review Python code for correctness, style, and edge cases. "
                        "Report any issues found."
                    ),
                    "description": "Reviews Python code quality and correctness.",
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Create sort.py with bubble_sort(arr) and quick_sort(arr) functions, "
            "then have the code-reviewer check the implementation.",
        )
        assert result.success, f"Failed: {result.error}"
        assert list(tmp_path.rglob("sort.py")), "sort.py was not created"

        # Subagent invocation is non-deterministic — validate structure only when it occurs
        for invocation in result.subagent_invocations:
            assert invocation.name, "SubagentInvocation.name must not be empty"
            assert invocation.status in ("selected", "started", "completed", "failed"), (
                f"Unexpected SubagentInvocation.status: {invocation.status!r}"
            )
