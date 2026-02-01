"""Agent execution engine with retry support."""

from __future__ import annotations

import asyncio
import functools
import json
import os
import time
from typing import TYPE_CHECKING, Any, Callable

import litellm
from litellm.exceptions import RateLimitError as LiteLLMRateLimitError

from pytest_aitest.core.errors import EngineTimeoutError, RateLimitError
from pytest_aitest.core.result import AgentResult, ToolCall, Turn
from pytest_aitest.execution.retry import RetryConfig, with_retry
from pytest_aitest.execution.skill_tools import (
    execute_skill_tool,
    get_skill_tools_schema,
    is_skill_tool,
)

if TYPE_CHECKING:
    from pytest_aitest.core.agent import Agent
    from pytest_aitest.execution.servers import ServerManager


@functools.cache
def _get_azure_ad_token_provider() -> Callable[[], str] | None:
    """Get Azure AD token provider for Entra ID authentication.

    Uses LiteLLM's built-in helper which leverages DefaultAzureCredential.
    Cached at module level to avoid recreating credentials on each call.
    - Azure CLI credentials (az login)
    - Managed Identity
    - Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, ...)
    - Visual Studio Code credentials
    """
    try:
        from litellm.secret_managers.get_azure_ad_token_provider import (
            get_azure_ad_token_provider,
        )

        return get_azure_ad_token_provider()
    except ImportError:
        # azure-identity not installed
        return None
    except Exception:
        # Credential not available
        return None


class AgentEngine:
    """Executes agent interactions with tool servers.

    Example:
        engine = AgentEngine(agent, server_manager)
        await engine.initialize()
        result = await engine.run("What's the weather?")
        await engine.shutdown()
    """

    def __init__(
        self,
        agent: Agent,
        server_manager: ServerManager,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.agent = agent
        self.server_manager = server_manager
        self.retry_config = retry_config or RetryConfig()
        self._tools: list[dict[str, Any]] = []
        self._azure_ad_token_provider: Callable[[], str] | None = None

    async def initialize(self) -> None:
        """Start servers and collect available tools."""
        await self.server_manager.start_all()
        self._tools = await self.server_manager.get_tools_schema()

        # Add skill reference tools if skill has references
        if self.agent.skill and self.agent.skill.has_references:
            skill_tools = get_skill_tools_schema(self.agent.skill)
            self._tools.extend(skill_tools)

        # Auto-configure Azure Entra ID when using Azure model without API key
        provider = self.agent.provider
        if provider.model.startswith("azure/") and not os.environ.get("AZURE_API_KEY"):
            self._azure_ad_token_provider = _get_azure_ad_token_provider()

    async def shutdown(self) -> None:
        """Stop all servers."""
        await self.server_manager.stop_all()

    async def run(
        self,
        prompt: str,
        *,
        max_turns: int | None = None,
        timeout_ms: int = 60000,
    ) -> AgentResult:
        """Run the agent with the given prompt.

        Args:
            prompt: User prompt to send to the agent
            max_turns: Maximum conversation turns (overrides agent config)
            timeout_ms: Timeout in milliseconds for the entire run

        Returns:
            AgentResult with conversation history and tool calls
        """
        max_turns = max_turns or self.agent.max_turns
        turns: list[Turn] = []
        total_tokens: dict[str, int] = {"prompt": 0, "completion": 0}
        total_cost: float = 0.0
        start_time = time.perf_counter()

        # Build system prompt: skill content (if any) + agent's system prompt
        system_prompt = self._build_system_prompt()

        # Build initial messages
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        turns.append(Turn(role="user", content=prompt))

        try:
            async with asyncio.timeout(timeout_ms / 1000):
                for _turn_num in range(max_turns):
                    # Call LLM with retry
                    response = await self._call_llm_with_retry(messages)

                    # Track tokens
                    if hasattr(response, "usage") and response.usage:
                        total_tokens["prompt"] += response.usage.prompt_tokens or 0
                        total_tokens["completion"] += response.usage.completion_tokens or 0

                    # Track cost (LiteLLM provides this in _hidden_params)
                    if hasattr(response, "_hidden_params"):
                        cost = response._hidden_params.get("response_cost", 0.0)
                        if cost:
                            total_cost += float(cost)

                    choice = response.choices[0]
                    assistant_msg = choice.message

                    # Check for tool calls
                    if assistant_msg.tool_calls:
                        tool_calls = await self._execute_tool_calls(assistant_msg.tool_calls)
                        content = assistant_msg.content or ""
                        turns.append(Turn(role="assistant", content=content, tool_calls=tool_calls))

                        # Add assistant message and tool results to context
                        messages.append(assistant_msg.model_dump())
                        for tc, call in zip(assistant_msg.tool_calls, tool_calls, strict=True):
                            result_content = call.error if call.error else call.result
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tc.id,
                                    "content": result_content or "",
                                }
                            )
                    else:
                        # Final response (no tool calls)
                        content = assistant_msg.content or ""
                        turns.append(Turn(role="assistant", content=content))
                        break

                    # Check finish reason
                    if choice.finish_reason == "stop":
                        break

        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            error = EngineTimeoutError(timeout_ms, len(turns))
            return AgentResult(
                turns=turns,
                success=False,
                error=str(error),
                duration_ms=duration_ms,
                token_usage=total_tokens,
                cost_usd=total_cost,
            )
        except RateLimitError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                turns=turns,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                token_usage=total_tokens,
                cost_usd=total_cost,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                turns=turns,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                token_usage=total_tokens,
                cost_usd=total_cost,
            )

        duration_ms = (time.perf_counter() - start_time) * 1000
        return AgentResult(
            turns=turns,
            success=True,
            duration_ms=duration_ms,
            token_usage=total_tokens,
            cost_usd=total_cost,
        )

    def _build_system_prompt(self) -> str | None:
        """Build the complete system prompt with skill content prepended."""
        parts: list[str] = []

        # Skill content comes first
        if self.agent.skill:
            parts.append(self.agent.skill.content)

        # Then agent's custom system prompt
        if self.agent.system_prompt:
            parts.append(self.agent.system_prompt)

        if not parts:
            return None

        return "\n\n".join(parts)

    async def _call_llm_with_retry(self, messages: list[dict[str, Any]]) -> Any:
        """Call the LLM with retry logic for rate limits."""
        return await with_retry(
            lambda: self._call_llm(messages),
            config=self.retry_config,
        )

    async def _call_llm(self, messages: list[dict[str, Any]]) -> Any:
        """Call the LLM with current messages and tools."""
        provider = self.agent.provider
        kwargs: dict[str, Any] = {
            "model": provider.model,
            "messages": messages,
        }

        # LiteLLM reads api_key/api_base from environment automatically
        if provider.temperature is not None:
            kwargs["temperature"] = provider.temperature
        if provider.max_tokens:
            kwargs["max_tokens"] = provider.max_tokens

        # Rate limiting - LiteLLM handles queuing automatically
        if provider.rpm is not None:
            kwargs["rpm"] = provider.rpm
        if provider.tpm is not None:
            kwargs["tpm"] = provider.tpm

        # Use Azure AD token provider for Entra ID auth
        if self._azure_ad_token_provider is not None:
            kwargs["azure_ad_token_provider"] = self._azure_ad_token_provider

        if self._tools:
            kwargs["tools"] = self._tools
            kwargs["tool_choice"] = "auto"

        try:
            return await litellm.acompletion(**kwargs)
        except LiteLLMRateLimitError as e:
            # Convert to our error type for consistent handling
            retry_after = getattr(e, "retry_after", None)
            raise RateLimitError(retry_after) from e

    async def _execute_tool_calls(self, tool_calls: list[Any]) -> list[ToolCall]:
        """Execute tool calls and return results."""
        results = []
        for tc in tool_calls:
            name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)

                # Handle skill reference tools separately
                if is_skill_tool(name) and self.agent.skill:
                    result = execute_skill_tool(self.agent.skill, name, arguments)
                else:
                    result = await self.server_manager.call_tool(name, arguments)

                results.append(ToolCall(name=name, arguments=arguments, result=result))
            except json.JSONDecodeError as e:
                results.append(
                    ToolCall(name=name, arguments={}, error=f"Invalid JSON arguments: {e}")
                )
            except Exception as e:
                try:
                    arguments = json.loads(tc.function.arguments)
                except Exception:
                    arguments = {}
                results.append(ToolCall(name=name, arguments=arguments, error=str(e)))
        return results
