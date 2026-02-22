"""Tests for plugin JUnit XML enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field

from pytest_skill_engineering.core.eval import Eval, MCPServer, Provider, Wait
from pytest_skill_engineering.core.result import EvalResult, SkillInfo, ToolCall, Turn
from pytest_skill_engineering.plugin import _add_junit_properties


@dataclass
class MockReport:
    """Mock pytest report with user_properties."""

    user_properties: list[tuple[str, str]] = field(default_factory=list)


class TestAddJunitProperties:
    """Tests for _add_junit_properties function."""

    def test_basic_agent_identity(self) -> None:
        """Test agent name and model are added."""
        report = MockReport()
        result = EvalResult(
            turns=[],
            success=True,
        )
        agent = Eval(
            name="test-agent",
            provider=Provider(model="azure/gpt-5-mini"),
        )

        _add_junit_properties(report, result, agent)

        props = dict(report.user_properties)
        assert props["aitest.agent.name"] == "test-agent"
        assert props["aitest.model"] == "gpt-5-mini"
        assert props["aitest.success"] == "true"

    def test_skill_info(self) -> None:
        """Test skill name is added."""
        report = MockReport()
        result = EvalResult(
            turns=[],
            success=True,
            skill_info=SkillInfo(
                name="financial-advisor",
                description="Financial advice",
                instruction_content="Expert financial advice",
            ),
        )

        _add_junit_properties(report, result, None)

        props = dict(report.user_properties)
        assert props["aitest.skill"] == "financial-advisor"

    def test_prompt_from_agent(self) -> None:
        """Test system prompt name from agent."""
        report = MockReport()
        result = EvalResult(turns=[], success=True)
        agent = Eval(
            provider=Provider(model="azure/gpt-5-mini"),
            system_prompt_name="concise",
        )

        _add_junit_properties(report, result, agent)

        props = dict(report.user_properties)
        assert props["aitest.prompt"] == "concise"

    def test_token_usage(self) -> None:
        """Test token counts are added."""
        report = MockReport()
        result = EvalResult(
            turns=[],
            success=True,
            token_usage={
                "prompt": 1250,
                "completion": 89,
            },
        )

        _add_junit_properties(report, result, None)

        props = dict(report.user_properties)
        assert props["aitest.tokens.input"] == "1250"
        assert props["aitest.tokens.output"] == "89"
        assert props["aitest.tokens.total"] == "1339"

    def test_cost(self) -> None:
        """Test cost is added with proper formatting."""
        report = MockReport()
        result = EvalResult(
            turns=[],
            success=True,
            cost_usd=0.000425,
        )

        _add_junit_properties(report, result, None)

        props = dict(report.user_properties)
        assert props["aitest.cost_usd"] == "0.000425"

    def test_turns_count(self) -> None:
        """Test turn count is added."""
        report = MockReport()
        result = EvalResult(
            turns=[
                Turn(role="user", content="Hello"),
                Turn(role="assistant", content="Hi there"),
                Turn(role="user", content="Thanks"),
            ],
            success=True,
        )

        _add_junit_properties(report, result, None)

        props = dict(report.user_properties)
        assert props["aitest.turns"] == "3"

    def test_tools_called(self) -> None:
        """Test tools called are listed."""
        report = MockReport()
        result = EvalResult(
            turns=[
                Turn(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(name="get_balance", arguments={"account": "checking"}),
                        ToolCall(
                            name="transfer",
                            arguments={
                                "from_account": "checking",
                                "to_account": "savings",
                                "amount": 100,
                            },
                        ),
                    ],
                ),
                Turn(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(name="get_balance", arguments={"account": "savings"}),
                    ],
                ),
            ],
            success=True,
        )

        _add_junit_properties(report, result, None)

        props = dict(report.user_properties)
        # Should be unique and sorted
        assert props["aitest.tools.called"] == "get_balance,transfer"

    def test_failure_status(self) -> None:
        """Test failed agent shows false."""
        report = MockReport()
        result = EvalResult(turns=[], success=False, error="Timeout")

        _add_junit_properties(report, result, None)

        props = dict(report.user_properties)
        assert props["aitest.success"] == "false"

    def test_no_user_properties_attribute(self) -> None:
        """Test graceful handling when report lacks user_properties."""

        class BareReport:
            pass

        report = BareReport()
        result = EvalResult(turns=[], success=True)

        # Should not raise
        _add_junit_properties(report, result, None)

    def test_full_example(self) -> None:
        """Test complete example with all fields populated."""
        report = MockReport()
        result = EvalResult(
            turns=[
                Turn(
                    role="assistant",
                    content="Checking balance: $1,500",
                    tool_calls=[ToolCall(name="get_balance", arguments={"account": "checking"})],
                ),
            ],
            success=True,
            skill_info=SkillInfo(name="financial-advisor", description="", instruction_content=""),
            token_usage={"prompt": 500, "completion": 50},
            cost_usd=0.00125,
        )
        agent = Eval(
            name="banking-agent",
            provider=Provider(model="azure/gpt-5-mini"),
            system_prompt_name="detailed",
        )

        _add_junit_properties(report, result, agent)

        props = dict(report.user_properties)
        assert props["aitest.agent.name"] == "banking-agent"
        assert props["aitest.model"] == "gpt-5-mini"
        assert props["aitest.skill"] == "financial-advisor"
        assert props["aitest.prompt"] == "detailed"
        assert props["aitest.tokens.input"] == "500"
        assert props["aitest.tokens.output"] == "50"
        assert props["aitest.tokens.total"] == "550"
        assert props["aitest.cost_usd"] == "0.001250"
        assert props["aitest.turns"] == "1"
        assert props["aitest.tools.called"] == "get_balance"
        assert props["aitest.success"] == "true"

    def test_mcp_servers(self) -> None:
        """Test MCP server names are added from agent config."""
        report = MockReport()
        result = EvalResult(turns=[], success=True)
        agent = Eval(
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[
                MCPServer(
                    command=["python", "-m", "banking_mcp"],
                    wait=Wait.for_tools(["get_balance"]),
                ),
                MCPServer(
                    command=["python", "-m", "calendar_mcp"],
                    wait=Wait.for_tools(["create_event"]),
                ),
            ],
        )

        _add_junit_properties(report, result, agent)

        props = dict(report.user_properties)
        assert props["aitest.servers"] == "banking_mcp,calendar_mcp"

    def test_allowed_tools(self) -> None:
        """Test allowed_tools filter is added from agent config."""
        report = MockReport()
        result = EvalResult(turns=[], success=True)
        agent = Eval(
            provider=Provider(model="azure/gpt-5-mini"),
            allowed_tools=["get_balance", "transfer"],
        )

        _add_junit_properties(report, result, agent)

        props = dict(report.user_properties)
        assert props["aitest.allowed_tools"] == "get_balance,transfer"

    def test_full_example_with_agent(self) -> None:
        """Test complete example with agent config included."""
        report = MockReport()
        result = EvalResult(
            turns=[
                Turn(
                    role="assistant",
                    content="Checking balance: $1,500",
                    tool_calls=[ToolCall(name="get_balance", arguments={"account": "checking"})],
                ),
            ],
            success=True,
            skill_info=SkillInfo(name="financial-advisor", description="", instruction_content=""),
            token_usage={"prompt": 500, "completion": 50},
            cost_usd=0.00125,
        )
        agent = Eval(
            name="banking-agent",
            provider=Provider(model="azure/gpt-5-mini"),
            system_prompt_name="detailed",
            mcp_servers=[
                MCPServer(command=["python", "-m", "banking_mcp"], wait=Wait.ready()),
            ],
            allowed_tools=["get_balance", "transfer"],
        )

        _add_junit_properties(report, result, agent)

        props = dict(report.user_properties)
        assert props["aitest.agent.name"] == "banking-agent"
        assert props["aitest.model"] == "gpt-5-mini"
        assert props["aitest.servers"] == "banking_mcp"
        assert props["aitest.allowed_tools"] == "get_balance,transfer"
        assert props["aitest.success"] == "true"
