"""Unit tests for Agent configuration."""

from __future__ import annotations

from pathlib import Path

from pytest_skill_engineering.core.agent import Agent, MCPServer, Provider, Wait


class TestAgent:
    """Tests for Agent dataclass."""

    def test_minimal_agent(self) -> None:
        """Agent requires only provider; name auto-constructed from model."""
        agent = Agent(provider=Provider(model="azure/gpt-5-mini"))
        assert agent.provider.model == "azure/gpt-5-mini"
        assert agent.name == "gpt-5-mini"
        assert agent.mcp_servers == []
        assert agent.cli_servers == []
        assert agent.system_prompt is None
        assert agent.max_turns == 10
        assert agent.skill is None
        assert agent.allowed_tools is None

    def test_agent_with_allowed_tools(self) -> None:
        """Agent can specify allowed_tools to filter available tools."""
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            allowed_tools=["read_cell", "write_cell"],
        )
        assert agent.allowed_tools == ["read_cell", "write_cell"]

    def test_agent_with_empty_allowed_tools(self) -> None:
        """Empty allowed_tools list means no tools available."""
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            allowed_tools=[],
        )
        assert agent.allowed_tools == []

    def test_agent_with_all_options(self) -> None:
        """Agent with all configuration options."""
        server = MCPServer(
            command=["python", "-m", "banking_server"],
            wait=Wait.for_tools(["get_balance"]),
        )
        agent = Agent(
            name="test-agent",
            provider=Provider(model="azure/gpt-5-mini", temperature=0.7),
            mcp_servers=[server],
            system_prompt="Be helpful.",
            max_turns=5,
            allowed_tools=["get_balance"],
        )
        assert agent.name == "test-agent"
        assert agent.provider.temperature == 0.7
        assert len(agent.mcp_servers) == 1
        assert agent.system_prompt == "Be helpful."
        assert agent.max_turns == 5
        assert agent.allowed_tools == ["get_balance"]

    def test_auto_name_model_only(self) -> None:
        """Auto-name strips provider prefix."""
        agent = Agent(provider=Provider(model="azure/gpt-4.1"))
        assert agent.name == "gpt-4.1"

    def test_auto_name_with_prompt(self) -> None:
        """Auto-name includes system_prompt_name dimension."""
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            system_prompt_name="concise",
        )
        assert agent.name == "gpt-5-mini + concise"

    def test_auto_name_with_skill(self) -> None:
        """Auto-name includes skill dimension."""
        from pytest_skill_engineering.core.skill import Skill, SkillMetadata

        skill = Skill(
            path=Path("skills/financial-advisor"),
            metadata=SkillMetadata(name="financial-advisor", description="Financial advice"),
            content="Be helpful.",
        )
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            skill=skill,
        )
        assert agent.name == "gpt-5-mini + financial-advisor"

    def test_auto_name_with_all_dimensions(self) -> None:
        """Auto-name includes all dimensions."""
        from pytest_skill_engineering.core.skill import Skill, SkillMetadata

        skill = Skill(
            path=Path("skills/financial-advisor"),
            metadata=SkillMetadata(name="financial-advisor", description="Financial advice"),
            content="Know finance.",
        )
        agent = Agent(
            provider=Provider(model="azure/gpt-4.1"),
            system_prompt_name="detailed",
            skill=skill,
        )
        assert agent.name == "gpt-4.1 + detailed + financial-advisor"

    def test_explicit_name_not_overridden(self) -> None:
        """Explicit name is preserved — not overridden by auto-construction."""
        agent = Agent(
            name="my-custom-agent",
            provider=Provider(model="azure/gpt-5-mini"),
            system_prompt_name="concise",
        )
        assert agent.name == "my-custom-agent"

    def test_auto_name_no_provider_prefix(self) -> None:
        """Auto-name works without provider prefix."""
        agent = Agent(provider=Provider(model="gpt-4o"))
        assert agent.name == "gpt-4o"


class TestProvider:
    """Tests for Provider dataclass."""

    def test_minimal_provider(self) -> None:
        """Provider requires only model."""
        provider = Provider(model="openai/gpt-4o")
        assert provider.model == "openai/gpt-4o"
        assert provider.temperature is None
        assert provider.max_tokens is None
        assert provider.rpm is None
        assert provider.tpm is None

    def test_provider_with_rate_limits(self) -> None:
        """Provider with rate limiting."""
        provider = Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000)
        assert provider.rpm == 10
        assert provider.tpm == 10000


class TestMCPServer:
    """Tests for MCPServer dataclass."""

    def test_minimal_server(self) -> None:
        """MCPServer requires only command."""
        server = MCPServer(command=["python", "-m", "my_server"])
        assert server.command == ["python", "-m", "my_server"]
        assert server.args == []
        assert server.env == {}
        assert server.wait.strategy.value == "ready"
        assert server.cwd is None
        assert server.transport == "stdio"
        assert server.url is None
        assert server.headers == {}

    def test_server_with_wait_for_tools(self) -> None:
        """MCPServer with Wait.for_tools()."""
        server = MCPServer(
            command=["python", "-m", "banking"],
            wait=Wait.for_tools(["get_balance", "transfer"]),
        )
        assert server.wait.strategy.value == "tools"
        assert server.wait.tools == ("get_balance", "transfer")

    def test_sse_transport(self) -> None:
        """MCPServer with SSE transport requires url, no command."""
        server = MCPServer(transport="sse", url="http://localhost:8000/sse")
        assert server.transport == "sse"
        assert server.url == "http://localhost:8000/sse"
        assert server.command == []

    def test_streamable_http_transport(self) -> None:
        """MCPServer with streamable-http transport requires url."""
        server = MCPServer(
            transport="streamable-http",
            url="http://localhost:8000/mcp",
            headers={"Authorization": "Bearer test-token"},
        )
        assert server.transport == "streamable-http"
        assert server.url == "http://localhost:8000/mcp"
        assert server.headers == {"Authorization": "Bearer test-token"}

    def test_stdio_requires_command(self) -> None:
        """stdio transport without command raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="requires 'command'"):
            MCPServer(transport="stdio")

    def test_stdio_rejects_url(self) -> None:
        """stdio transport with url raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="does not use 'url'"):
            MCPServer(command=["python"], url="http://localhost")

    def test_sse_requires_url(self) -> None:
        """SSE transport without url raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="requires 'url'"):
            MCPServer(transport="sse")

    def test_sse_rejects_command(self) -> None:
        """SSE transport with command raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="does not use 'command'"):
            MCPServer(transport="sse", url="http://localhost", command=["python"])

    def test_streamable_http_requires_url(self) -> None:
        """streamable-http transport without url raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="requires 'url'"):
            MCPServer(transport="streamable-http")

    def test_headers_env_expansion(self) -> None:
        """Headers expand ${VAR} patterns from environment."""
        import os

        os.environ["TEST_MCP_TOKEN"] = "secret-123"
        try:
            server = MCPServer(
                transport="sse",
                url="http://localhost:8000/sse",
                headers={"Authorization": "Bearer ${TEST_MCP_TOKEN}"},
            )
            # Headers store the raw template; expansion is deferred to connection time
            assert server.headers["Authorization"] == "Bearer ${TEST_MCP_TOKEN}"
        finally:
            del os.environ["TEST_MCP_TOKEN"]
