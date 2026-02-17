"""Agent execution engine powered by Pydantic AI."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import UsageLimits

from pytest_aitest.core.result import (
    AgentResult,
    ClarificationStats,
    SkillInfo,
    ToolInfo,
)
from pytest_aitest.execution.clarification import check_clarification
from pytest_aitest.execution.pydantic_adapter import (
    adapt_result,
    build_mcp_toolsets,
    build_pydantic_agent,
    build_system_prompt,
)
from pytest_aitest.execution.rate_limiter import get_rate_limiter

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pydantic_ai import Agent as PydanticAgent
    from pydantic_ai.toolsets import AbstractToolset

    from pytest_aitest.core.agent import Agent


class AgentEngine:
    """Executes agent interactions using Pydantic AI.

    Example:
        engine = AgentEngine(agent)
        await engine.initialize()
        result = await engine.run("What's my checking balance?")
        await engine.shutdown()
    """

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self._pydantic_agent: PydanticAgent[None, str] | None = None
        self._toolsets: list[AbstractToolset[Any]] = []
        self._exit_stack: contextlib.AsyncExitStack | None = None
        self._available_tools: list[ToolInfo] = []
        self._skill_info: SkillInfo | None = None
        self._effective_system_prompt: str = ""
        self._rate_limiter = get_rate_limiter(
            agent.provider.model,
            rpm=agent.provider.rpm,
            tpm=agent.provider.tpm,
        )

    async def initialize(self) -> None:
        """Build PydanticAI agent with MCP toolsets and start servers."""
        self._exit_stack = contextlib.AsyncExitStack()

        # Build MCP toolsets from our MCPServer configs
        mcp_toolsets = build_mcp_toolsets(self.agent.mcp_servers, max_retries=self.agent.retries)
        self._toolsets.extend(mcp_toolsets)

        # Build CLI toolset if needed
        if self.agent.cli_servers:
            from pytest_aitest.execution.cli_toolset import CLIToolset

            cli_toolset = CLIToolset(self.agent.cli_servers, max_retries=self.agent.retries)
            self._toolsets.append(cli_toolset)

        # Build skill reference tools as a FunctionToolset if skill has references
        if self.agent.skill and self.agent.skill.has_references:
            skill_toolset = self._build_skill_toolset()
            if skill_toolset:
                self._toolsets.append(skill_toolset)

        # Build PydanticAI agent
        self._pydantic_agent = build_pydantic_agent(self.agent, self._toolsets)

        try:
            # Enter the agent context (starts MCP servers, etc.)
            await self._exit_stack.enter_async_context(self._pydantic_agent)

            # Collect tool info for AI analysis after servers are started
            self._available_tools = await self._collect_tool_info()
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            raise

        # Build SkillInfo for AI analysis
        if self.agent.skill:
            self._skill_info = SkillInfo(
                name=self.agent.skill.name,
                description=self.agent.skill.metadata.description,
                instruction_content=self.agent.skill.content,
                reference_names=list(self.agent.skill.references.keys()),
            )

        # Store effective system prompt
        prompt = build_system_prompt(self.agent)
        if prompt:
            self._effective_system_prompt = prompt

    async def shutdown(self) -> None:
        """Stop all servers and clean up."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                _logger.debug("Engine cleanup error", exc_info=True)
            finally:
                self._exit_stack = None
        self._pydantic_agent = None

    async def run(
        self,
        prompt: str,
        *,
        max_turns: int | None = None,
        timeout_ms: int = 60000,
        messages: list[Any] | None = None,
    ) -> AgentResult:
        """Run the agent with the given prompt.

        Args:
            prompt: User prompt to send to the agent
            max_turns: Maximum conversation turns (overrides agent config)
            timeout_ms: Timeout in milliseconds for the entire run
            messages: Optional prior PydanticAI messages for session continuity.

        Returns:
            AgentResult with conversation history and tool calls
        """
        assert self._pydantic_agent is not None, "Engine not initialized"

        max_turns = max_turns or self.agent.max_turns
        start_time = time.perf_counter()
        session_context_count = len(messages) if messages else 0

        # Messages are PydanticAI ModelMessage objects — pass directly
        message_history: list[ModelMessage] | None = messages if messages else None

        usage_limits = UsageLimits(request_limit=max_turns)

        try:
            import asyncio

            # Enforce rate limits (rpm/tpm) before making the API call
            if self._rate_limiter.has_limits:
                await self._rate_limiter.acquire()

            async with asyncio.timeout(timeout_ms / 1000):
                result = await self._pydantic_agent.run(
                    prompt,
                    message_history=message_history,
                    usage_limits=usage_limits,
                )

            # Record token usage for tpm tracking
            run_usage = result.usage()
            total_tokens = (run_usage.input_tokens or 0) + (run_usage.output_tokens or 0)
            if total_tokens > 0:
                self._rate_limiter.record_tokens(total_tokens)

            # Build AgentResult from PydanticAI result
            agent_result = adapt_result(
                result,
                start_time=start_time,
                model=self.agent.provider.model,
                available_tools=self._available_tools,
                skill_info=self._skill_info,
                effective_system_prompt=self._effective_system_prompt,
                session_context_count=session_context_count,
            )

            # Post-processing: clarification detection
            if self.agent.clarification_detection.enabled:
                agent_result.clarification_stats = await self._run_clarification_detection(
                    agent_result
                )

            return agent_result

        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                turns=[],
                success=False,
                error=f"Engine timed out after {timeout_ms}ms",
                duration_ms=duration_ms,
                available_tools=self._available_tools,
                skill_info=self._skill_info,
                effective_system_prompt=self._effective_system_prompt,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                turns=[],
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                available_tools=self._available_tools,
                skill_info=self._skill_info,
                effective_system_prompt=self._effective_system_prompt,
            )

    async def _run_clarification_detection(self, result: AgentResult) -> ClarificationStats:
        """Run clarification detection on the final response."""
        from pytest_aitest.execution.pydantic_adapter import build_model_from_string

        stats = ClarificationStats()
        final = result.final_response
        if not final or not final.strip():
            return stats

        detection = self.agent.clarification_detection

        # Build a PydanticAI model for the judge — supports Azure Entra ID
        judge_model_str = detection.judge_model or self.agent.provider.model
        judge_model = build_model_from_string(judge_model_str)

        is_clarification = await check_clarification(
            final,
            judge_model=judge_model,
        )
        if is_clarification:
            stats.count = 1
            stats.turn_indices = [len(result.turns) - 1]
            preview = final[:200] + "..." if len(final) > 200 else final
            stats.examples = [preview]

        return stats

    async def _collect_tool_info(self) -> list[ToolInfo]:
        """Collect ToolInfo from all toolsets for AI analysis."""
        tools_info: list[ToolInfo] = []

        if not self._pydantic_agent:
            return tools_info

        # Get tools from the PydanticAI agent's combined toolset
        try:
            from pydantic_ai.tools import RunContext

            # Create a minimal context to query tools
            # We iterate through our toolsets directly instead
            for toolset in self._toolsets:
                toolset_name = getattr(toolset, "id", None) or type(toolset).__name__
                try:
                    ctx = RunContext[None](
                        deps=None,
                        model=None,  # type: ignore[arg-type]
                        usage=None,  # type: ignore[arg-type]
                        prompt="",
                        run_step=0,
                        retry=0,
                        tool_name=None,
                        tool_call_id=None,
                    )
                    tools = await toolset.get_tools(ctx)
                    for name, tool in tools.items():
                        tools_info.append(
                            ToolInfo(
                                name=name,
                                description=tool.tool_def.description or "",
                                input_schema=tool.tool_def.parameters_json_schema or {},
                                server_name=toolset_name,
                            )
                        )
                except Exception:
                    _logger.debug(
                        "Failed to collect tool info from %s", toolset_name, exc_info=True
                    )
        except Exception:
            _logger.debug("Failed to collect tool info", exc_info=True)

        return tools_info

    def _build_skill_toolset(self) -> AbstractToolset[Any] | None:
        """Build a FunctionToolset for skill reference tools."""
        if not self.agent.skill or not self.agent.skill.has_references:
            return None

        from pytest_aitest.execution.skill_tools import execute_skill_tool

        skill = self.agent.skill

        from pydantic_ai import FunctionToolset

        toolset = FunctionToolset(id="skill-references")

        @toolset.tool  # type: ignore[misc]
        def list_skill_references() -> str:
            """List available reference documents for the skill."""
            return execute_skill_tool(skill, "list_skill_references", {})

        @toolset.tool  # type: ignore[misc]
        def read_skill_reference(filename: str) -> str:
            """Read a reference document from the skill."""
            return execute_skill_tool(skill, "read_skill_reference", {"filename": filename})

        return toolset
