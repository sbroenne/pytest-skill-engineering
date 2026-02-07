"""AI-powered insights generation for test reports."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import litellm
from litellm.exceptions import RateLimitError

from pytest_aitest.core.auth import get_azure_ad_token_provider

if TYPE_CHECKING:
    from pytest_aitest.core.result import SkillInfo, ToolInfo
    from pytest_aitest.reporting.collector import SuiteReport


@dataclass(slots=True)
class InsightsResult:
    """Result of AI insights generation.

    Contains the markdown analysis and metadata about the generation.
    """

    markdown_summary: str
    model: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    cached: bool = False


_logger = logging.getLogger(__name__)

# Load the analysis prompt template
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "ai_summary.md"


def _load_analysis_prompt() -> str:
    """Load the analysis prompt template."""
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    # Fallback minimal prompt
    return "Analyze these test results and provide actionable feedback in markdown format."


def _build_analysis_input(
    suite_report: SuiteReport,
    tool_info: list[ToolInfo],
    skill_info: list[SkillInfo],
    prompts: dict[str, str],
    *,
    min_pass_rate: int | None = None,
) -> str:
    """Build the complete analysis input with all context."""
    sections = []

    # Pass rate threshold
    if min_pass_rate is not None:
        sections.append(f"## Minimum Pass Rate Threshold: {min_pass_rate}%\n")
        sections.append(
            f"Agents with pass rate below {min_pass_rate}% are **disqualified**. "
            "Exclude disqualified agents from your Recommendation. "
            "Do not recommend a disqualified agent for deployment. "
            "Still analyze their failures in the Failure Analysis section.\n"
        )

    # Test results summary
    sections.append("## Test Results\n")
    for test in suite_report.tests:
        sections.append(f"### {test.name}")
        sections.append(f"- Outcome: {test.outcome}")
        if test.docstring:
            sections.append(f"- Description: {test.docstring}")
        if test.error:
            sections.append(f"- Error: {test.error}")
        if test.agent_result:
            ar = test.agent_result
            # Include agent identity for this specific test (from TestReport, not AgentResult)
            if test.agent_name:
                sections.append(f"- Agent: {test.agent_name}")
            if test.model:
                sections.append(f"- Model: {test.model}")
            if ar.skill_info:
                sections.append(f"- Skill: {ar.skill_info.name}")
            sections.append(f"- Duration: {ar.duration_ms:.0f}ms")
            # token_usage is a dict with 'prompt', 'completion' keys
            total_tokens = ar.token_usage.get("prompt", 0) + ar.token_usage.get("completion", 0)
            sections.append(f"- Tokens: {total_tokens}")
            sections.append(f"- Cost: ${ar.cost_usd:.6f}")
            if ar.tool_names_called:
                sections.append(f"- Tools called: {', '.join(ar.tool_names_called)}")
            # Include system prompt excerpt if present
            if ar.effective_system_prompt:
                prompt_excerpt = ar.effective_system_prompt[:300]
                if len(ar.effective_system_prompt) > 300:
                    prompt_excerpt += "..."
                sections.append(f"- System prompt: {prompt_excerpt}")
            # Include conversation
            sections.append("\n**Conversation:**")
            for turn in ar.turns:
                role = turn.role.upper()
                content = turn.content[:500] + "..." if len(turn.content) > 500 else turn.content
                sections.append(f"[{role}] {content}")
                if turn.tool_calls:
                    for tc in turn.tool_calls:
                        if tc.result and len(tc.result) > 500:
                            result = tc.result[:500] + "..."
                        else:
                            result = tc.result
                        sections.append(f"  → {tc.name}({json.dumps(tc.arguments)}) = {result}")
        sections.append("")

    # MCP tool definitions
    if tool_info:
        sections.append("\n## MCP Tools\n")
        for tool in tool_info:
            sections.append(f"### {tool.name} (from {tool.server_name})")
            sections.append(f"Description: {tool.description}")
            sections.append(f"Schema: {json.dumps(tool.input_schema, indent=2)}")
            sections.append("")

    # Skill content
    if skill_info:
        sections.append("\n## Skills\n")
        for skill in skill_info:
            sections.append(f"### {skill.name}")
            sections.append(f"Description: {skill.description}")
            if skill.reference_names:
                sections.append(f"References: {', '.join(skill.reference_names)}")
            sections.append(f"\n**Content:**\n{skill.instruction_content[:2000]}")
            sections.append("")

    # Prompt variants
    if prompts:
        sections.append("\n## Prompt Variants\n")
        for name, content in prompts.items():
            sections.append(f"### {name}")
            sections.append(f"```\n{content[:1000]}\n```")
            sections.append("")

    return "\n".join(sections)


def _get_results_hash(suite_report: SuiteReport) -> str:
    """Generate a hash of test results for caching."""
    # Hash key fields that affect analysis
    hash_content = {
        "tests": [
            {
                "name": t.name,
                "outcome": t.outcome,
                "error": t.error,
            }
            for t in suite_report.tests
        ],
        "summary": {
            "total": suite_report.total,
            "passed": suite_report.passed,
            "failed": suite_report.failed,
        },
    }
    content = json.dumps(hash_content, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


async def generate_insights(
    suite_report: SuiteReport,
    tool_info: list[ToolInfo] | None = None,
    skill_info: list[SkillInfo] | None = None,
    prompts: dict[str, str] | None = None,
    model: str = "azure/gpt-5-mini",
    cache_dir: Path | None = None,
    min_pass_rate: int | None = None,
) -> InsightsResult:
    """Generate AI insights markdown from test results.

    Args:
        suite_report: The complete test suite report
        tool_info: MCP tool definitions (optional)
        skill_info: Skill metadata (optional)
        prompts: Prompt variants by name (optional)
        model: LiteLLM model to use for analysis
        cache_dir: Directory for caching results (optional)
        min_pass_rate: Minimum pass rate threshold for disqualifying agents

    Returns:
        InsightsResult with markdown summary and generation metadata.

    Raises:
        InsightsGenerationError: If AI analysis fails after retries
    """
    import asyncio

    # Check cache first
    results_hash = _get_results_hash(suite_report)
    cache_path = cache_dir / f".aitest_cache_{results_hash}.json" if cache_dir else None

    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            return InsightsResult(
                markdown_summary=cached.get("insights", ""),
                model=cached.get("model", model),
                tokens_used=cached.get("tokens_used", 0),
                cost_usd=cached.get("cost_usd", 0.0),
                duration_ms=cached.get("duration_ms", 0.0),
                cached=True,
            )
        except Exception:
            _logger.debug("Cache invalid, regenerating insights", exc_info=True)

    # Build prompt - LLM returns markdown directly
    prompt_template = _load_analysis_prompt()

    # Build analysis input
    analysis_input = _build_analysis_input(
        suite_report=suite_report,
        tool_info=tool_info or [],
        skill_info=skill_info or [],
        prompts=prompts or {},
        min_pass_rate=min_pass_rate,
    )

    full_prompt = f"{prompt_template}\n\n---\n\n# Test Data\n\n{analysis_input}"

    # Call LLM with retry
    start_time = time.perf_counter()
    total_tokens = 0
    total_cost = 0.0

    # Get Azure AD token provider for authentication
    azure_ad_token_provider = get_azure_ad_token_provider()

    for attempt in range(3):
        try:
            # Build kwargs for litellm - no response_format, LLM returns markdown
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": full_prompt}],
            }

            # Add Azure AD token provider if available
            if azure_ad_token_provider is not None:
                kwargs["azure_ad_token_provider"] = azure_ad_token_provider

            response = await litellm.acompletion(**kwargs)

            # Track usage
            total_tokens = 0
            total_cost = 0.0
            if hasattr(response, "usage") and response.usage:  # type: ignore[union-attr]
                usage = response.usage  # type: ignore[union-attr]
                total_tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
            if hasattr(response, "_hidden_params"):
                total_cost = response._hidden_params.get("response_cost", 0.0) or 0.0

            # Get markdown content directly from LLM response
            markdown_content = response.choices[0].message.content or ""  # type: ignore[union-attr]

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Save to cache
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_data = {
                    "insights": markdown_content,
                    "model": model,
                    "tokens_used": total_tokens,
                    "cost_usd": total_cost,
                    "duration_ms": duration_ms,
                }
                cache_path.write_text(json.dumps(cache_data))

            return InsightsResult(
                markdown_summary=markdown_content,
                model=model,
                tokens_used=total_tokens,
                cost_usd=total_cost,
                duration_ms=duration_ms,
                cached=False,
            )

        except RateLimitError as e:
            if attempt < 2:
                await asyncio.sleep(2**attempt)
                continue
            raise InsightsGenerationError(f"Rate limited after {attempt + 1} attempts") from e
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(1)
                continue
            raise InsightsGenerationError(f"AI analysis failed: {e}") from e

    # Should not reach here, but just in case
    raise InsightsGenerationError("AI analysis failed after all retries")


class InsightsGenerationError(Exception):
    """Raised when AI insights generation fails."""
