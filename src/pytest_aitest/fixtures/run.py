"""Agent run fixture."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING, Any

import pytest

from pytest_aitest.core.agent import Agent
from pytest_aitest.core.result import AgentResult
from pytest_aitest.execution.engine import AgentEngine
from pytest_aitest.execution.servers import ServerManager

if TYPE_CHECKING:
    pass


@pytest.fixture
def aitest_run(
    request: pytest.FixtureRequest,
) -> Callable[..., Any]:
    """Fixture providing a function to run agent interactions.

    Works seamlessly with pytest.mark.parametrize for model/prompt comparison:

    Example:
        @pytest.mark.parametrize("model", ["openai/gpt-4o", "openai/gpt-4o-mini"])
        async def test_model_comparison(aitest_run, model):
            agent = Agent(
                provider=Provider(model=model),
                system_prompt="You are a helpful assistant.",
            )
            result = await aitest_run(agent, "Hello!")
            assert result.success

        @pytest.mark.parametrize("prompt", [PROMPT_V1, PROMPT_V2])
        async def test_prompt_comparison(aitest_run, prompt):
            agent = Agent(
                provider=Provider(model="openai/gpt-4o-mini"),
                system_prompt=prompt.system_prompt,
            )
            result = await aitest_run(agent, "Hello!")
            assert result.success
    """
    engines: list[AgentEngine] = []
    results: list[AgentResult] = []

    async def run_agent(
        agent: Agent,
        prompt: str,
        *,
        max_turns: int | None = None,
        timeout_ms: int = 60000,
    ) -> AgentResult:
        """Run an agent with the given prompt.

        Args:
            agent: Agent configuration with provider and servers
            prompt: User prompt to send
            max_turns: Maximum conversation turns (default: agent.max_turns)
            timeout_ms: Timeout for the entire run (default: 60000)

        Returns:
            AgentResult with conversation history and tool calls
        """
        server_manager = ServerManager(
            mcp_servers=agent.mcp_servers,
            cli_servers=agent.cli_servers,
        )
        engine = AgentEngine(agent, server_manager)
        engines.append(engine)

        await engine.initialize()
        result = await engine.run(prompt, max_turns=max_turns, timeout_ms=timeout_ms)

        # Store result for reporting
        results.append(result)
        # Store the most recent result for the plugin to pick up
        request.node._aitest_result = result  # type: ignore[attr-defined]

        return result

    # Store engines for cleanup
    request.node._aitest_engines = engines  # type: ignore[attr-defined]

    return run_agent


@pytest.fixture(autouse=True)
async def _aitest_auto_cleanup(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[None, None]:
    """Automatically cleanup any agent engines after each test."""
    yield

    engines = getattr(request.node, "_aitest_engines", [])
    for engine in engines:
        try:
            await engine.shutdown()
        except Exception:
            pass  # Best effort cleanup
