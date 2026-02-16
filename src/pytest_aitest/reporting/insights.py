"""AI-powered insights generation for test reports."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_aitest.execution.cost import estimate_cost, models_without_pricing

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

    # Pricing completeness — warn AI when cost data is unreliable
    if models_without_pricing:
        models_list = ", ".join(sorted(models_without_pricing))
        sections.append("## ⚠️ Incomplete Pricing Data\n")
        sections.append(
            f"The following models have **no pricing data**: {models_list}\n\n"
            "Cost values for these models are $0.00 and **do not reflect reality**. "
            "Do NOT use cost as a ranking factor or mention cost savings/comparisons. "
            "Focus your analysis on pass rate, tool usage, and response quality instead. "
            "In the Winner Card, omit cost or mark it as 'N/A (pricing unavailable)'.\n"
        )

    # Pre-computed agent statistics for AI accuracy (grouped by agent name)
    agent_agg: dict[str, dict[str, Any]] = {}
    has_iterations = any(t.iteration is not None for t in suite_report.tests)
    for test in suite_report.tests:
        agent_name = test.agent_name or test.model or "unknown"
        if agent_name not in agent_agg:
            agent_agg[agent_name] = {
                "name": test.agent_name or test.model or "unknown",
                "passed": 0,
                "failed": 0,
                "total": 0,
                "cost": 0.0,
                "tokens": 0,
                "turn_counts": [],
                "iter_groups": {},  # test_base_name -> {"passed": int, "total": int}
            }
        agg = agent_agg[agent_name]
        agg["total"] += 1
        if test.outcome == "passed":
            agg["passed"] += 1
        else:
            agg["failed"] += 1
        if test.agent_result:
            agg["cost"] += test.agent_result.cost_usd or 0
            usage = test.agent_result.token_usage or {}
            agg["tokens"] += usage.get("prompt", 0) + usage.get("completion", 0)
            agg["turn_counts"].append(len(test.agent_result.turns))
        # Track iteration groups for flakiness detection
        if has_iterations and test.iteration is not None:
            # Strip "-iter-N" parametrize suffix to group by base test name
            base_name = re.sub(r"-iter-\d+\]$", "]", test.name)
            ig = agg["iter_groups"]
            if base_name not in ig:
                ig[base_name] = {"passed": 0, "total": 0}
            ig[base_name]["total"] += 1
            if test.outcome == "passed":
                ig[base_name]["passed"] += 1

    if agent_agg:
        # Rank: pass_rate desc → total tests desc → cost_per_test asc
        ranked = sorted(
            agent_agg.items(),
            key=lambda item: (
                -(item[1]["passed"] / max(item[1]["total"], 1) * 100),
                -item[1]["total"],
                item[1]["cost"] / max(item[1]["total"], 1),
            ),
        )

        # Aggregate stats
        all_turn_counts: list[int] = []
        for v in agent_agg.values():
            all_turn_counts.extend(v["turn_counts"])
        avg_turns = sum(all_turn_counts) / len(all_turn_counts) if all_turn_counts else 0

        sections.append("## Pre-computed Agent Statistics\n")
        sections.append(
            "Use these exact numbers in your Winner Card, metric cards, "
            "and Comparative Analysis. "
            "Do NOT re-derive statistics from raw test data — "
            "these are authoritative.\n"
        )

        sections.append("**Aggregate Stats:**")
        sections.append(f"- Total Test Executions: {suite_report.total}")
        sections.append(f"- Passed: {suite_report.passed}")
        sections.append(f"- Failed: {suite_report.failed}")
        sections.append(f"- Agent Configurations: {len(agent_agg)}")
        sections.append(f"- Avg Turns per Test: {avg_turns:.1f}")
        sections.append("")

        # Winner determination
        winner_name = None
        for _aid, st in ranked:
            rate = st["passed"] / max(st["total"], 1) * 100
            is_dq = min_pass_rate is not None and rate < min_pass_rate
            if not is_dq:
                winner_name = st["name"]
                sections.append(f"**Winner:** {st['name']}")
                sections.append(f"- Pass Rate: {rate:.0f}%")
                sections.append(f"- Tests: {st['passed']}/{st['total']}")
                sections.append(f"- Cost: ${st['cost']:.6f}")
                sections.append(f"- Tokens: {st['tokens']:,}")
                sections.append("")
                break

        # All agents ranked
        sections.append("**All Agents (ranked):**\n")
        sections.append("| Rank | Agent | Pass Rate | Tests | Cost | Tokens | Status |")
        sections.append("|------|-------|-----------|-------|------|--------|--------|")
        for rank, (_aid, st) in enumerate(ranked, 1):
            rate = st["passed"] / max(st["total"], 1) * 100
            is_dq = min_pass_rate is not None and rate < min_pass_rate
            if st["name"] == winner_name:
                status = "✅ Winner"
            elif is_dq:
                status = "⛔ Disqualified"
            else:
                status = ""
            sections.append(
                f"| {rank} | {st['name']} | {rate:.0f}% | "
                f"{st['passed']}/{st['total']} | ${st['cost']:.6f} | "
                f"{st['tokens']:,} | {status} |"
            )
        sections.append("")

        # Iteration statistics (when --aitest-iterations was used)
        if has_iterations:
            sections.append("**Iteration Statistics:**\n")
            for _aid, st in ranked:
                ig = st.get("iter_groups", {})
                if not ig:
                    continue
                total_iter_passed = sum(g["passed"] for g in ig.values())
                total_iter_count = sum(g["total"] for g in ig.values())
                iter_rate = total_iter_passed / max(total_iter_count, 1) * 100
                sections.append(
                    f"- {st['name']}: Iter Pass Rate: {iter_rate:.0f}% "
                    f"({total_iter_passed}/{total_iter_count})"
                )
                # Flag flaky tests (<100% iteration pass rate)
                flaky = [
                    (name, g)
                    for name, g in ig.items()
                    if g["passed"] < g["total"] and g["passed"] > 0
                ]
                if flaky:
                    for fname, fg in flaky:
                        sections.append(
                            f"  - ⚠️ Flaky: {fname} ({fg['passed']}/{fg['total']} iterations passed)"
                        )
            sections.append("")

    # Compute max iteration count for tagging
    max_iter = 1
    if has_iterations:
        iter_vals = [t.iteration for t in suite_report.tests if t.iteration is not None]
        max_iter = max(iter_vals) if iter_vals else 1

    # Test results summary
    sections.append("## Test Results\n")
    for test in suite_report.tests:
        # Use human-readable name: docstring if available, else short test name
        header = f"### {test.display_name}"
        if has_iterations and test.iteration is not None:
            header += f" [iter {test.iteration}/{max_iter}]"
        sections.append(header)
        if test.class_docstring:
            sections.append(f"- Group: {test.class_docstring.split(chr(10))[0].strip()}")
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
            # Include LLM score data when available
            if test.assertions:
                for assertion in test.assertions:
                    if assertion.get("type") == "llm_score":
                        total = assertion.get("total", 0)
                        max_total = assertion.get("max_total", 0)
                        pct = assertion.get("weighted_score", 0)
                        sections.append(f"- LLM Score: {total}/{max_total} ({pct:.0%})")
                        dims = assertion.get("dimensions", [])
                        for d in dims:
                            sections.append(f"  - {d['name']}: {d['score']}/{d['max_score']}")
                        reasoning = assertion.get("details", "")
                        if reasoning:
                            sections.append(f"  - Reasoning: {reasoning[:300]}")
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

        # Compute tool coverage: which tools were never called across all tests
        all_tool_names = {t.name for t in tool_info}
        called_tool_names: set[str] = set()
        for test in suite_report.tests:
            if test.agent_result:
                called_tool_names.update(test.agent_result.tool_names_called)
        uncalled_tools = sorted(all_tool_names - called_tool_names)
        if uncalled_tools:
            sections.append("## Tool Coverage\n")
            sections.append(
                f"The following tools were available but never called across all tests: "
                f"{', '.join(uncalled_tools)}"
            )
            sections.append(
                "\nNote: This is only a concern if tests were expected to exercise these tools. "
                "If no test asserts on these tools, this is a coverage observation, not a failure."
            )
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
    analysis_prompt: str | None = None,
) -> InsightsResult:
    """Generate AI insights markdown from test results.

    Args:
        suite_report: The complete test suite report
        tool_info: MCP tool definitions (optional)
        skill_info: Skill metadata (optional)
        prompts: Prompt variants by name (optional)
        model: Model identifier (e.g., "azure/gpt-5-mini", "openai/gpt-5-mini")
        cache_dir: Directory for caching results (optional)
        min_pass_rate: Minimum pass rate threshold for disqualifying agents
        analysis_prompt: Custom analysis prompt text. If None, uses the built-in
            default from prompts/ai_summary.md. Downstream plugins can provide
            domain-specific prompts via the ``pytest_aitest_analysis_prompt`` hook.

    Returns:
        InsightsResult with markdown summary and generation metadata.

    Raises:
        InsightsGenerationError: If AI analysis fails after retries
    """
    import asyncio

    from pydantic_ai import Agent as PydanticAgent

    from pytest_aitest.execution.pydantic_adapter import build_model_from_string

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
    prompt_template = analysis_prompt if analysis_prompt else _load_analysis_prompt()

    # Build analysis input
    analysis_input = _build_analysis_input(
        suite_report=suite_report,
        tool_info=tool_info or [],
        skill_info=skill_info or [],
        prompts=prompts or {},
        min_pass_rate=min_pass_rate,
    )

    full_prompt = f"{prompt_template}\n\n---\n\n# Test Data\n\n{analysis_input}"

    # Build PydanticAI model
    pydantic_model = build_model_from_string(model)

    # Create a simple PydanticAI agent for analysis
    analysis_agent = PydanticAgent(pydantic_model, output_type=str)

    # Call with retry
    start_time = time.perf_counter()

    for attempt in range(3):
        try:
            result = await analysis_agent.run(full_prompt)

            # Track usage
            usage = result.usage()
            input_tokens = usage.input_tokens or 0
            output_tokens = usage.output_tokens or 0
            total_tokens = input_tokens + output_tokens
            insights_cost = estimate_cost(model, input_tokens, output_tokens)

            markdown_content = result.output
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Save to cache
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_data = {
                    "insights": markdown_content,
                    "model": model,
                    "tokens_used": total_tokens,
                    "cost_usd": insights_cost,
                    "duration_ms": duration_ms,
                }
                cache_path.write_text(json.dumps(cache_data))

            return InsightsResult(
                markdown_summary=markdown_content,
                model=model,
                tokens_used=total_tokens,
                cost_usd=insights_cost,
                duration_ms=duration_ms,
                cached=False,
            )

        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2**attempt)
                continue
            raise InsightsGenerationError(f"AI analysis failed: {e}") from e

    # Should not reach here, but just in case
    raise InsightsGenerationError("AI analysis failed after all retries")


class InsightsGenerationError(Exception):
    """Raised when AI insights generation fails."""
