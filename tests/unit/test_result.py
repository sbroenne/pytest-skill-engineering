"""Tests for pytest-skill-engineering result models."""

from __future__ import annotations

from pytest_skill_engineering.core.result import (
    CustomAgentInfo,
    EvalResult,
    MCPPrompt,
    MCPPromptArgument,
    ToolCall,
    Turn,
)


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_success(self) -> None:
        tc = ToolCall(name="read_file", arguments={"path": "/tmp/test.txt"}, result="file contents")
        assert tc.name == "read_file"
        assert tc.result == "file contents"
        assert tc.error is None

    def test_error(self) -> None:
        tc = ToolCall(name="read_file", arguments={"path": "/nonexistent"}, error="File not found")
        assert tc.error == "File not found"
        assert tc.result is None

    def test_repr_ok(self) -> None:
        tc = ToolCall(name="read_file", arguments={}, result="ok")
        assert "read_file" in repr(tc)
        assert "ok" in repr(tc)

    def test_repr_error(self) -> None:
        tc = ToolCall(name="read_file", arguments={}, error="fail")
        assert "error" in repr(tc)


class TestTurn:
    """Tests for Turn dataclass."""

    def test_user_turn(self) -> None:
        turn = Turn(role="user", content="Hello!")
        assert turn.role == "user"
        assert turn.text == "Hello!"
        assert turn.tool_calls == []

    def test_assistant_turn_with_tools(self) -> None:
        tc = ToolCall(name="search", arguments={"q": "test"}, result="found")
        turn = Turn(role="assistant", content="Let me search...", tool_calls=[tc])
        assert len(turn.tool_calls) == 1
        assert turn.tool_calls[0].name == "search"

    def test_repr_truncation(self) -> None:
        long_content = "A" * 100
        turn = Turn(role="assistant", content=long_content)
        repr_str = repr(turn)
        assert "..." in repr_str  # Should be truncated


class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_success(self) -> None:
        turns = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", content="Hi there!"),
        ]
        result = EvalResult(turns=turns, success=True, duration_ms=100.0)

        assert result.success
        assert bool(result) is True
        assert result.error is None

    def test_failure(self) -> None:
        result = EvalResult(turns=[], success=False, error="Timeout")
        assert not result.success
        assert bool(result) is False
        assert result.error == "Timeout"

    def test_final_response(self) -> None:
        turns = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", content="First response"),
            Turn(role="user", content="More"),
            Turn(role="assistant", content="Final response"),
        ]
        result = EvalResult(turns=turns, success=True)
        assert result.final_response == "Final response"

    def test_final_response_empty(self) -> None:
        result = EvalResult(turns=[], success=True)
        assert result.final_response == ""

    def test_all_responses(self) -> None:
        turns = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", content="Response 1"),
            Turn(role="user", content="More"),
            Turn(role="assistant", content="Response 2"),
        ]
        result = EvalResult(turns=turns, success=True)
        assert result.all_responses == ["Response 1", "Response 2"]

    def test_all_tool_calls(self) -> None:
        tc1 = ToolCall(name="tool1", arguments={}, result="r1")
        tc2 = ToolCall(name="tool2", arguments={}, result="r2")
        turns = [
            Turn(role="assistant", content="", tool_calls=[tc1]),
            Turn(role="assistant", content="", tool_calls=[tc2]),
        ]
        result = EvalResult(turns=turns, success=True)

        assert len(result.all_tool_calls) == 2
        assert result.tool_names_called == {"tool1", "tool2"}

    def test_tool_was_called(self) -> None:
        tc = ToolCall(name="read_file", arguments={}, result="ok")
        turns = [Turn(role="assistant", content="", tool_calls=[tc])]
        result = EvalResult(turns=turns, success=True)

        assert result.tool_was_called("read_file")
        assert not result.tool_was_called("write_file")

    def test_tool_calls_for(self) -> None:
        tc1 = ToolCall(name="read_file", arguments={"path": "a.txt"}, result="a")
        tc2 = ToolCall(name="read_file", arguments={"path": "b.txt"}, result="b")
        tc3 = ToolCall(name="write_file", arguments={"path": "c.txt"}, result="ok")
        turns = [Turn(role="assistant", content="", tool_calls=[tc1, tc2, tc3])]
        result = EvalResult(turns=turns, success=True)

        read_calls = result.tool_calls_for("read_file")
        assert len(read_calls) == 2
        assert all(c.name == "read_file" for c in read_calls)

    def test_repr(self) -> None:
        turns = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", content="Hi there!"),
        ]
        result = EvalResult(turns=turns, success=True, duration_ms=150.5)

        repr_str = repr(result)
        assert "SUCCESS" in repr_str
        assert "150" in repr_str
        assert "Hi there!" in repr_str

    def test_repr_failure(self) -> None:
        result = EvalResult(turns=[], success=False, error="Network error")
        repr_str = repr(result)
        assert "FAILED" in repr_str
        assert "Network error" in repr_str

    def test_session_not_continuation(self) -> None:
        """Test fresh conversation has no session context."""
        result = EvalResult(
            turns=[Turn(role="user", content="Hello")],
            success=True,
            session_context_count=0,
        )
        assert not result.is_session_continuation
        assert result.session_context_count == 0

    def test_session_continuation(self) -> None:
        """Test conversation with prior messages is a session continuation."""
        result = EvalResult(
            turns=[Turn(role="user", content="Follow up")],
            success=True,
            session_context_count=5,  # 5 prior messages
        )
        assert result.is_session_continuation
        assert result.session_context_count == 5

    def test_messages_property_returns_copy(self) -> None:
        """Test messages property returns a copy to prevent mutation."""
        original_messages = [{"role": "user", "content": "Hello"}]
        result = EvalResult(
            turns=[Turn(role="user", content="Hello")],
            success=True,
            _messages=original_messages,
        )

        # Get messages and modify
        messages_copy = result.messages
        messages_copy.append({"role": "assistant", "content": "Hi"})

        # Original should be unchanged
        assert len(result._messages) == 1
        assert len(result.messages) == 1


class TestEvalResultNewFields:
    """Tests for new EvalResult fields added in the latest API."""

    def test_mcp_prompts_default_empty(self) -> None:
        """mcp_prompts defaults to empty list."""
        result = EvalResult(turns=[], success=True)
        assert result.mcp_prompts == []

    def test_mcp_prompts_set(self) -> None:
        """mcp_prompts can be populated with MCPPrompt instances."""
        arg = MCPPromptArgument(name="language", description="Target language", required=True)
        prompt = MCPPrompt(name="translate", description="Translate text", arguments=[arg])
        result = EvalResult(turns=[], success=True, mcp_prompts=[prompt])
        assert len(result.mcp_prompts) == 1
        assert result.mcp_prompts[0].name == "translate"
        assert result.mcp_prompts[0].description == "Translate text"
        assert result.mcp_prompts[0].arguments[0].name == "language"
        assert result.mcp_prompts[0].arguments[0].required is True

    def test_prompt_name_default_none(self) -> None:
        """prompt_name defaults to None."""
        result = EvalResult(turns=[], success=True)
        assert result.prompt_name is None

    def test_prompt_name_set(self) -> None:
        """prompt_name can be set to track the prompt file used."""
        result = EvalResult(turns=[], success=True, prompt_name="review")
        assert result.prompt_name == "review"

    def test_custom_agent_info_default_none(self) -> None:
        """custom_agent_info defaults to None."""
        result = EvalResult(turns=[], success=True)
        assert result.custom_agent_info is None

    def test_custom_agent_info_set(self) -> None:
        """custom_agent_info can be set with CustomAgentInfo."""
        info = CustomAgentInfo(
            name="reviewer",
            description="Code reviewer agent",
            file_path=".github/agents/reviewer.agent.md",
        )
        result = EvalResult(turns=[], success=True, custom_agent_info=info)
        assert result.custom_agent_info is not None
        assert result.custom_agent_info.name == "reviewer"
        assert result.custom_agent_info.description == "Code reviewer agent"
        assert result.custom_agent_info.file_path == ".github/agents/reviewer.agent.md"

    def test_premium_requests_default_zero(self) -> None:
        """premium_requests defaults to 0.0."""
        result = EvalResult(turns=[], success=True)
        assert result.premium_requests == 0.0

    def test_premium_requests_set(self) -> None:
        """premium_requests tracks Copilot billing units."""
        result = EvalResult(turns=[], success=True, premium_requests=2.5)
        assert result.premium_requests == 2.5

    def test_mcp_prompt_repr(self) -> None:
        """MCPPrompt repr includes name and argument count."""
        prompt = MCPPrompt(name="summarize", arguments=[MCPPromptArgument(name="text")])
        r = repr(prompt)
        assert "summarize" in r
        assert "1 args" in r

    def test_mcp_prompt_argument_repr(self) -> None:
        """MCPPromptArgument repr includes name and required flag."""
        arg = MCPPromptArgument(name="query", required=True)
        r = repr(arg)
        assert "query" in r
        assert "required" in r

    def test_custom_agent_info_repr(self) -> None:
        """CustomAgentInfo repr includes name."""
        info = CustomAgentInfo(name="coder")
        r = repr(info)
        assert "coder" in r
