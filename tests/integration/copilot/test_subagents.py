"""Subagent dispatch tests.

Proves that the subagent dispatch mechanism works reliably when the
orchestrator cannot implement directly (write tools excluded).

When the orchestrator has no write tools, it *must* route to a subagent
to produce file output. This makes dispatch deterministic and asserts:
- ``result.subagent_invocations`` is non-empty
- The subagent actually created the expected file
- ``SubagentInvocation`` objects have valid name/status fields
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

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


@pytest.mark.copilot
class TestForcedSubagentDispatch:
    """When write tools are excluded, the orchestrator must use runSubagent.

    These tests are deterministic: the orchestrator physically cannot create
    files, so it has no choice but to dispatch to the subagent that can.
    """

    async def test_subagent_invocations_non_empty(self, copilot_eval, tmp_path):
        """Orchestrator with excluded write tools dispatches to a subagent.

        With no write tools available, the orchestrator cannot create the
        requested file itself and must invoke the file-writer subagent.
        Asserts that at least one subagent invocation is recorded.
        """
        agent = CopilotEval(
            name="forced-orchestrator",
            instructions=(
                "You are an orchestrator. You MUST delegate all file creation "
                "to the file-writer agent via runSubagent. "
                "Do not attempt to create files yourself."
            ),
            working_directory=str(tmp_path),
            timeout_s=300.0,
            max_turns=20,
            excluded_tools=_WRITE_TOOLS,
            custom_agents=[
                {
                    "name": "file-writer",
                    "prompt": (
                        "You create Python files. When asked to create a file, "
                        "write it to disk using your file creation tools."
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
        """File created by subagent exists in the workspace.

        Complements test_subagent_invocations_non_empty by verifying the
        subagent actually produced the expected artifact.
        """
        agent = CopilotEval(
            name="forced-orchestrator-file",
            instructions=(
                "You are an orchestrator. Delegate all file creation to the "
                "file-writer agent via runSubagent."
            ),
            working_directory=str(tmp_path),
            timeout_s=300.0,
            max_turns=20,
            excluded_tools=_WRITE_TOOLS,
            custom_agents=[
                {
                    "name": "file-writer",
                    "prompt": ("You create Python files. Write requested files to disk."),
                    "description": "Creates Python source files on disk.",
                }
            ],
        )
        result = await copilot_eval(
            agent,
            "Use the file-writer agent to create output.py containing: x = 42",
        )
        assert result.success, f"Run failed: {result.error}"
        assert (tmp_path / "output.py").exists(), (
            "output.py not created — subagent did not write the file"
        )

    async def test_subagent_invocation_fields(self, copilot_eval, tmp_path):
        """SubagentInvocation objects have valid name and status fields."""
        agent = CopilotEval(
            name="forced-orchestrator-fields",
            instructions=(
                "You are an orchestrator. Delegate file creation to the "
                "file-writer agent via runSubagent."
            ),
            working_directory=str(tmp_path),
            timeout_s=300.0,
            max_turns=20,
            excluded_tools=_WRITE_TOOLS,
            custom_agents=[
                {
                    "name": "file-writer",
                    "prompt": "You create Python files on disk.",
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
