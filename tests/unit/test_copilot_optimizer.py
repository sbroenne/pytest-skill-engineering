"""Unit tests for optimize_instruction() and InstructionSuggestion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_skill_engineering import InstructionSuggestion, optimize_instruction
from pytest_skill_engineering.copilot.result import CopilotResult, ToolCall, Turn

# Patch targets — the optimizer now lives in pytest_skill_engineering
_AGENT_PATCH = "pytest_skill_engineering.execution.optimizer.PydanticAgent"
_BUILD_MODEL_PATCH = "pytest_skill_engineering.execution.optimizer.build_model_from_string"
_FAKE_MODEL = MagicMock(name="fake-model")


def _make_result(
    *,
    success: bool = True,
    final_response: str = "Here is the code.",
    tools: list[str] | None = None,
) -> CopilotResult:
    tool_calls = [ToolCall(name=t, arguments={}) for t in (tools or [])]
    return CopilotResult(
        success=success,
        turns=[Turn(role="assistant", content=final_response, tool_calls=tool_calls)],
    )


def _make_agent_mock(instruction: str, reasoning: str, changes: str) -> MagicMock:
    """Return a MagicMock that behaves like pydantic-ai Eval class."""
    output = MagicMock(instruction=instruction, reasoning=reasoning, changes=changes)
    run_result = MagicMock(output=output)
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=run_result)
    return MagicMock(return_value=agent_instance)


class TestInstructionSuggestion:
    """Tests for the InstructionSuggestion dataclass."""

    def test_str_contains_instruction(self):
        s = InstructionSuggestion(
            instruction="Always add docstrings.",
            reasoning="The original instruction omits documentation requirements.",
            changes="Added docstring mandate.",
        )
        assert "Always add docstrings." in str(s)

    def test_str_contains_reasoning(self):
        s = InstructionSuggestion(instruction="inst", reasoning="because reasons", changes="x")
        assert "because reasons" in str(s)

    def test_str_contains_changes(self):
        s = InstructionSuggestion(
            instruction="inst", reasoning="reason", changes="Added docstring mandate."
        )
        assert "Added docstring mandate." in str(s)

    def test_fields_accessible(self):
        s = InstructionSuggestion(instruction="inst", reasoning="reason", changes="changes")
        assert s.instruction == "inst"
        assert s.reasoning == "reason"
        assert s.changes == "changes"


class TestOptimizeInstruction:
    """Tests for optimize_instruction()."""

    async def test_returns_instruction_suggestion(self):
        agent_class = _make_agent_mock(
            instruction="Always add Google-style docstrings.",
            reasoning="The original instruction omits documentation.",
            changes="Added docstring mandate.",
        )
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            result = await optimize_instruction(
                "Write Python code.", _make_result(), "Eval should add docstrings."
            )
        assert isinstance(result, InstructionSuggestion)
        assert result.instruction == "Always add Google-style docstrings."
        assert result.reasoning == "The original instruction omits documentation."
        assert result.changes == "Added docstring mandate."

    async def test_uses_default_model(self):
        """optimize_instruction defaults to azure/gpt-5.2-chat."""
        agent_class = _make_agent_mock("inst", "reason", "changes")
        with (
            patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL) as mock_build,
            patch(_AGENT_PATCH, agent_class),
        ):
            await optimize_instruction("inst", _make_result(), "criterion")
        mock_build.assert_called_once_with("azure/gpt-5.2-chat")
        assert agent_class.call_args[0][0] is _FAKE_MODEL

    async def test_accepts_custom_model_string(self):
        """optimize_instruction passes model string through build_model_from_string."""
        agent_class = _make_agent_mock("inst", "reason", "changes")
        with (
            patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL) as mock_build,
            patch(_AGENT_PATCH, agent_class),
        ):
            await optimize_instruction(
                "inst", _make_result(), "criterion", model="openai/gpt-4o-mini"
            )
        mock_build.assert_called_once_with("openai/gpt-4o-mini")

    async def test_accepts_model_object(self):
        """optimize_instruction skips build_model_from_string for a pre-built Model object."""
        agent_class = _make_agent_mock("inst", "reason", "changes")
        fake_model = MagicMock()
        with patch(_BUILD_MODEL_PATCH) as mock_build, patch(_AGENT_PATCH, agent_class):
            await optimize_instruction("inst", _make_result(), "criterion", model=fake_model)
        mock_build.assert_not_called()
        assert agent_class.call_args[0][0] is fake_model

    async def test_includes_criterion_in_prompt(self):
        agent_class = _make_agent_mock("improved", "reason", "change")
        agent_instance = agent_class.return_value
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            await optimize_instruction(
                "Write code.", _make_result(), "Eval must use type hints on all functions."
            )
        assert "type hints" in agent_instance.run.call_args[0][0]

    async def test_includes_current_instruction_in_prompt(self):
        agent_class = _make_agent_mock("inst", "reason", "changes")
        agent_instance = agent_class.return_value
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            await optimize_instruction(
                "Always use FastAPI for web APIs.", _make_result(), "criterion"
            )
        assert "FastAPI" in agent_instance.run.call_args[0][0]

    async def test_includes_agent_output_in_prompt(self):
        agent_class = _make_agent_mock("inst", "reason", "changes")
        agent_instance = agent_class.return_value
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            await optimize_instruction(
                "inst", _make_result(final_response="def add(a, b): return a + b"), "criterion"
            )
        assert "def add" in agent_instance.run.call_args[0][0]

    async def test_handles_no_final_response(self):
        agent_class = _make_agent_mock("inst", "reason", "changes")
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            result = await optimize_instruction(
                "inst", CopilotResult(success=False, turns=[]), "criterion"
            )
        assert isinstance(result, InstructionSuggestion)

    async def test_handles_empty_instruction(self):
        agent_class = _make_agent_mock("new inst", "reason", "changes")
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            result = await optimize_instruction("", _make_result(), "criterion")
        assert isinstance(result, InstructionSuggestion)

    async def test_includes_tool_calls_in_prompt(self):
        agent_class = _make_agent_mock("inst", "reason", "changes")
        agent_instance = agent_class.return_value
        with patch(_BUILD_MODEL_PATCH, return_value=_FAKE_MODEL), patch(_AGENT_PATCH, agent_class):
            await optimize_instruction(
                "inst", _make_result(tools=["create_file", "read_file"]), "criterion"
            )
        assert "create_file" in agent_instance.run.call_args[0][0]
