"""Report generation helpers for the aitest pytest plugin.

Contains AI insights generation, analysis prompt resolution, copilot model
cleanup, and the coding-agent analysis prompt hook logic. Extracted from
``plugin.py`` for readability.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.terminal import TerminalReporter

    from pytest_skill_engineering.reporting import SuiteReport
    from pytest_skill_engineering.reporting.insights import InsightsResult


def log_report_path(config: Config, format_name: str, path: Path) -> None:
    """Log report path to terminal."""
    terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin("terminalreporter")
    if terminalreporter:
        terminalreporter.write_line(f"aitest {format_name} report: {path}")


def resolve_analysis_prompt(config: Config) -> str | None:
    """Resolve the analysis prompt from CLI option, plugin hook, or default.

    Priority: CLI option > plugin hook > None (let insights.py use built-in).
    """
    # 1. CLI option takes highest precedence
    prompt_path = config.getoption("--aitest-analysis-prompt", default=None)
    if prompt_path:
        path = Path(prompt_path)
        if not path.exists():
            raise pytest.UsageError(f"Analysis prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    # 2. Plugin hook (firstresult=True — first non-None wins)
    result = config.pluginmanager.hook.pytest_skill_engineering_analysis_prompt(config=config)
    if result:
        return result

    # 3. Fall back to built-in default (None signals insights.py to use its default)
    return None


def get_analysis_prompt_details(config: Config) -> tuple[str, str, str | None]:
    """Get effective analysis prompt text and metadata for current config.

    Returns:
        tuple of ``(prompt_text, source, path)`` where:
        - ``source`` is one of: ``cli-file``, ``hook``, ``built-in``
        - ``path`` is set only when source is ``cli-file``
    """
    prompt_path = config.getoption("--aitest-analysis-prompt", default=None)
    if prompt_path:
        path = Path(prompt_path)
        if not path.exists():
            raise pytest.UsageError(f"Analysis prompt file not found: {path}")
        return path.read_text(encoding="utf-8"), "cli-file", str(path)

    result = config.pluginmanager.hook.pytest_skill_engineering_analysis_prompt(config=config)
    if result:
        return result, "hook", None

    from pytest_skill_engineering.reporting.insights import _load_analysis_prompt

    return _load_analysis_prompt(), "built-in", None


def get_analysis_prompt(config: Config) -> str:
    """Get the effective analysis prompt text for the current pytest config.

    Resolution order:
    1. ``--aitest-analysis-prompt`` file content
    2. ``pytest_skill_engineering_analysis_prompt`` hook result
    3. Built-in default prompt from ``prompts/ai_summary.md``
    """
    prompt, _, _ = get_analysis_prompt_details(config)
    return prompt


def generate_structured_insights(
    config: Config, report: SuiteReport, *, required: bool = False
) -> InsightsResult | None:
    """Generate structured AI insights from test results.

    Args:
        config: pytest config
        report: Suite report with test results
        required: If True, raise error when model not configured (for report generation)

    Returns:
        InsightsResult or None if generation fails/skipped.

    Raises:
        pytest.UsageError: If required=True and model not configured.
    """
    import asyncio

    try:
        from pytest_skill_engineering.reporting.insights import generate_insights

        # Require dedicated summary model - no fallback
        model = config.getoption("--aitest-summary-model")
        if not model:
            if required:
                raise pytest.UsageError(
                    "AI analysis is required for report generation.\n"
                    "Please specify --aitest-summary-model with a capable model.\n"
                    "Example: --aitest-summary-model=azure/gpt-4.1\n"
                    "         --aitest-summary-model=openai/gpt-4o"
                )
            return None

        # Collect tool info and skill info from test results
        tool_info: list[Any] = []
        skill_info: list[Any] = []
        mcp_prompt_info: list[Any] = []
        custom_agent_info: list[Any] = []
        prompt_names: list[str] = []
        instruction_file_info: list[Any] = []
        prompts: dict[str, str] = {}

        for test in report.tests:
            if test.eval_result:
                # Collect tools (deduplicate by name)
                seen_tools = {t.name for t in tool_info}
                for t in getattr(test.eval_result, "available_tools", []) or []:
                    if t.name not in seen_tools:
                        tool_info.append(t)
                        seen_tools.add(t.name)

                # Collect MCP prompts (deduplicate by name)
                seen_mcp_prompts = {p.name for p in mcp_prompt_info}
                for p in getattr(test.eval_result, "mcp_prompts", []) or []:
                    if p.name not in seen_mcp_prompts:
                        mcp_prompt_info.append(p)
                        seen_mcp_prompts.add(p.name)

                # Collect skills (deduplicate by name)
                skill = getattr(test.eval_result, "skill_info", None)
                if skill and skill.name not in {s.name for s in skill_info}:
                    skill_info.append(skill)

                # Collect custom agent info (deduplicate by name)
                ca = getattr(test.eval_result, "custom_agent_info", None)
                if ca and ca.name not in {c.name for c in custom_agent_info}:
                    custom_agent_info.append(ca)

                # Collect prompt names used
                pn = getattr(test.eval_result, "prompt_name", None)
                if pn and pn not in prompt_names:
                    prompt_names.append(pn)

                # Collect instruction file info (deduplicate by name)
                for inf in getattr(test.eval_result, "instruction_files", []) or []:
                    if inf.name not in {i.name for i in instruction_file_info}:
                        instruction_file_info.append(inf)

                # Collect effective system prompts as prompt variants
                effective_prompt = getattr(test.eval_result, "effective_system_prompt", "")
                if effective_prompt:
                    prompt_label = test.system_prompt_name or "default"
                    if prompt_label not in prompts:
                        prompts[prompt_label] = effective_prompt

        # Generate insights using async function
        analysis_prompt, prompt_source, prompt_path = get_analysis_prompt_details(config)

        terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if config.getoption("--aitest-print-analysis-prompt") and terminalreporter:
            path_info = f", path={prompt_path}" if prompt_path else ""
            terminalreporter.write_line(
                f"aitest analysis prompt: source={prompt_source}{path_info}, "
                f"chars={len(analysis_prompt)}"
            )

        async def _run() -> InsightsResult:
            return await generate_insights(
                suite_report=report,
                tool_info=tool_info,
                skill_info=skill_info,
                mcp_prompt_info=mcp_prompt_info,
                custom_agent_info=custom_agent_info,
                prompt_names=prompt_names,
                instruction_file_info=instruction_file_info,
                prompts=prompts,
                model=model,
                min_pass_rate=config.getoption("--aitest-min-pass-rate"),
                analysis_prompt=analysis_prompt,
                compact=config.getoption("--aitest-summary-compact"),
            )

        # Use asyncio.run() instead of deprecated get_event_loop().run_until_complete()
        result = asyncio.run(_run())

        # Log generation stats
        if terminalreporter:
            tokens_str = f"{result.tokens_used:,}" if result.tokens_used else "N/A"
            cost_str = f"${result.cost_usd:.4f}" if result.cost_usd else "N/A"
            cached_str = " (cached)" if result.cached else ""
            terminalreporter.write_line(
                f"\nAI Insights generated{cached_str}: {tokens_str} tokens, {cost_str}"
            )

        return result

    except pytest.UsageError:
        # Re-raise configuration errors
        raise
    except Exception as e:
        terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if required:
            msg = (
                f"AI analysis failed (required for report generation): {e}\n"
                "JSON results were saved. Regenerate reports from JSON:\n"
                "  pytest-skill-engineering-report <json-path> --html report.html --summary"
            )
            if terminalreporter:
                terminalreporter.write_line(f"\nERROR: {msg}", red=True, bold=True)
            raise pytest.UsageError(msg) from e
        if terminalreporter:
            terminalreporter.write_line(f"Warning: AI insights generation failed: {e}")
        return None


def shutdown_copilot_model_client() -> None:
    """Shut down the shared CopilotClient if it was started."""
    try:
        from pytest_skill_engineering.copilot.model import (
            _client,
        )
        from pytest_skill_engineering.copilot.model import (
            shutdown_copilot_model_client as _shutdown,
        )

        if _client is not None:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_shutdown())
            finally:
                loop.close()
    except ImportError:
        pass


# ── Coding agent analysis prompt ──

_CODING_AGENT_ANALYSIS_PROMPT_PATH = Path(__file__).parent / "prompts" / "coding_agent_analysis.md"


def build_coding_agent_prompt(tests: list[Any]) -> str | None:
    """Return the coding-agent analysis prompt if copilot tests are detected.

    Checks if any collected tests have the ``_copilot_test`` flag. If so,
    returns the coding agent analysis prompt instead of the default MCP/tool
    prompt. The ``{{PRICING_TABLE}}`` placeholder is replaced with a live
    pricing table built from litellm.
    """
    has_copilot_tests = any(getattr(t, "_copilot_test", False) for t in tests)
    if not has_copilot_tests:
        return None

    if _CODING_AGENT_ANALYSIS_PROMPT_PATH.exists():
        prompt = _CODING_AGENT_ANALYSIS_PROMPT_PATH.read_text(encoding="utf-8")
        if "{{PRICING_TABLE}}" in prompt:
            prompt = prompt.replace("{{PRICING_TABLE}}", _build_pricing_table())
        return prompt
    return None


def _build_pricing_table() -> str:
    """Build a markdown pricing table from litellm's model_cost map.

    Returns a table of common coding-agent models with their per-token
    pricing, pulled live from litellm so it stays current.
    """
    try:
        from litellm import model_cost  # type: ignore[reportMissingImports]
    except ImportError:
        return "*Pricing data unavailable (litellm not installed).*"

    # Models we care about — bare names (no provider prefix).
    models_of_interest = [
        "gpt-4.1-nano",
        "gpt-5-nano",
        "gpt-4.1-mini",
        "gpt-5-mini",
        "gpt-4.1",
        "gpt-5",
        "gpt-5.1",
        "gpt-5.2",
        "claude-sonnet-4",
        "claude-sonnet-4-5",
        "claude-opus-4-5",
        "claude-opus-4-6",
        "gpt-5-pro",
        "gpt-5.2-pro",
    ]

    rows: list[str] = []
    for name in models_of_interest:
        info = model_cost.get(name) or model_cost.get(f"azure/{name}", {})
        ic = info.get("input_cost_per_token", 0) or 0
        oc = info.get("output_cost_per_token", 0) or 0
        if ic == 0 and oc == 0:
            continue
        rows.append(f"| {name} | ${ic * 1_000_000:.2f} | ${oc * 1_000_000:.2f} |")

    if not rows:
        return "*No model pricing data available from litellm.*"

    header = (
        "**Model pricing reference** ($/M tokens, from litellm):\n\n"
        "| Model | Input $/M | Output $/M |\n"
        "|-------|-----------|------------|\n"
    )
    return header + "\n".join(rows)
