"""Markdown report renderer using typed component functions.

Same architecture as htpy HTML components: typed functions that accept
dataclasses from components/types.py and return strings. Uses mdutils
for structural primitives (tables, headers).

This module mirrors the HTML report structure 1:1 so that the Markdown
report is functionally equivalent to the HTML report.
"""

from __future__ import annotations

from mdutils.tools.Header import AtxHeaderLevel, Header
from mdutils.tools.Table import Table

from pytest_aitest.reporting.components.types import (
    AgentData,
    ReportContext,
    ReportMetadata,
    TestData,
    TestGroupData,
    TestResultData,
    ToolCallData,
)

# Shorthand aliases for header levels
_H1 = AtxHeaderLevel.TITLE
_H2 = AtxHeaderLevel.HEADING
_H3 = AtxHeaderLevel.SUBHEADING
_H4 = AtxHeaderLevel.SUBSUBHEADING


def format_cost(cost: float) -> str:
    """Format cost in USD — shared with HTML components."""
    if cost == 0:
        return "N/A"
    if cost < 0.01:
        return f"${cost:.6f}"
    return f"${cost:.4f}"


# ---------------------------------------------------------------------------
# Report header
# ---------------------------------------------------------------------------


def _report_header(report: ReportMetadata) -> str:
    """Render the report title and metadata blockquote."""
    parts: list[str] = []

    parts.append(Header.atx(level=_H1, title=report.name))

    duration_s = report.duration_ms / 1000
    pass_rate = report.passed / report.total * 100 if report.total else 0

    # Cost breakdown
    test_run_cost = report.total_cost_usd
    if report.analysis_cost_usd:
        test_run_cost -= report.analysis_cost_usd
    test_run_cost = max(test_run_cost, 0.0)

    cost_parts = [f"🧪 {format_cost(test_run_cost)}"]
    if report.analysis_cost_usd:
        cost_parts.append(f"🤖 {format_cost(report.analysis_cost_usd)}")
    cost_parts.append(f"💰 {format_cost(report.total_cost_usd)}")

    parts.append(
        f"> **{report.total}** tests | "
        f"**{report.passed}** passed | "
        f"**{report.failed}** failed | "
        f"**{pass_rate:.0f}%** pass rate  "
    )
    parts.append(
        f"> Duration: {duration_s:.1f}s | "
        f"Cost: {' · '.join(cost_parts)} | "
        f"Tokens: {report.token_min:,}–{report.token_max:,}  "
    )
    parts.append(f"> {report.timestamp}")
    parts.append("")

    if report.suite_docstring:
        parts.append(f"*{report.suite_docstring}*")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Agent leaderboard
# ---------------------------------------------------------------------------


def _medal(rank: int) -> str:
    """Get medal emoji for rank."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(rank, str(rank))


def _agent_leaderboard_multi(agents: list[AgentData]) -> str:
    """Render ranked leaderboard table for multiple agents."""
    parts: list[str] = []
    parts.append(Header.atx(level=_H2, title="Agent Leaderboard"))

    # Build table data: header + rows
    header = ["#", "Agent", "Tests", "Pass Rate", "Tokens", "Cost", "Duration"]
    rows: list[list[str]] = [header]

    for i, agent in enumerate(agents, 1):
        rank = "⛔" if agent.disqualified else _medal(i)
        winner = " 🏆" if agent.is_winner else ""
        dq = " ~~disqualified~~" if agent.disqualified else ""
        name_col = f"{agent.name}{winner}{dq}"

        rows.append(
            [
                rank,
                name_col,
                f"{agent.passed}/{agent.total}",
                f"{agent.pass_rate:.0f}%",
                f"{agent.tokens:,}",
                format_cost(agent.cost),
                f"{agent.duration_s:.1f}s",
            ]
        )

    table = Table().create_table(
        columns=len(header),
        rows=len(rows),
        text=[cell for row in rows for cell in row],
        text_align=["center", "left", "center", "center", "right", "right", "right"],
    )
    parts.append(table)
    parts.append("")

    return "\n".join(parts)


def _agent_summary_card(agent: AgentData) -> str:
    """Render a single-agent summary card (blockquote)."""
    status = "✅ All Passed" if agent.pass_rate == 100 else f"❌ {agent.failed} Failed"

    return (
        f"> **{agent.name}** — {status}  \n"
        f"> {agent.passed}/{agent.total} tests | "
        f"{format_cost(agent.cost)} | "
        f"{agent.tokens:,} tokens | "
        f"{agent.duration_s:.1f}s\n"
    )


def _agent_leaderboard(agents: list[AgentData]) -> str:
    """Render the agent leaderboard section."""
    if not agents:
        return ""
    if len(agents) == 1:
        return _agent_summary_card(agents[0])
    return _agent_leaderboard_multi(agents)


# ---------------------------------------------------------------------------
# AI insights
# ---------------------------------------------------------------------------


def _ai_insights(markdown_summary: str | None) -> str:
    """Render the AI analysis section."""
    if not markdown_summary:
        return ""

    parts: list[str] = []
    parts.append(Header.atx(level=_H2, title="AI Analysis"))
    parts.append(markdown_summary)
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------


def _tool_calls_table(tool_calls: list[ToolCallData]) -> str:
    """Render a tool calls table."""
    if not tool_calls:
        return ""

    parts: list[str] = []
    parts.append("**Tool Calls:**")
    parts.append("")

    header = ["Tool", "Status", "Args"]
    rows: list[list[str]] = [header]

    for tc in tool_calls:
        status = "✅" if tc.success else f"❌ {tc.error or ''}"
        args_str = ""
        if tc.args:
            args_str = ", ".join(f"{k}={v!r}" for k, v in tc.args.items())
            if len(args_str) > 80:
                args_str = args_str[:77] + "..."
        rows.append([f"`{tc.name}`", status, args_str])

    table = Table().create_table(
        columns=len(header),
        rows=len(rows),
        text=[cell for row in rows for cell in row],
        text_align=["left", "center", "left"],
    )
    parts.append(table)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Test result detail
# ---------------------------------------------------------------------------


def _test_result_detail(
    result: TestResultData,
    agent_label: str,
    *,
    multi_agent: bool,
) -> str:
    """Render a single test result as a collapsible details block."""
    parts: list[str] = []

    # Summary line with metrics
    status_icon = "✅" if result.passed else "❌"
    metrics = (
        f"{result.duration_s:.1f}s · {result.tokens:,} tokens · "
        f"{result.turns} turns · {format_cost(result.cost)}"
    )

    if multi_agent:
        summary = f"{status_icon} {agent_label} — {metrics}"
    else:
        summary = metrics

    # Append iteration pass rate when aggregated across multiple runs
    if result.iterations and result.iteration_pass_rate is not None:
        n = len(result.iterations)
        n_passed = sum(1 for it in result.iterations if it.passed)
        summary += f" · {n_passed}/{n} iterations passed ({result.iteration_pass_rate:.0f}%)"

    parts.append("<details>")
    parts.append(f"<summary>{summary}</summary>")
    parts.append("")

    # Assertions
    if result.assertions:
        parts.append("**Assertions:**")
        parts.append("")
        for a in result.assertions:
            icon = "✅" if a.passed else "❌"
            parts.append(f"- {icon} `{a.type}`: {a.message}")
        parts.append("")

    # Scores
    if result.scores:
        parts.append("**Scores:**")
        parts.append("")
        for score in result.scores:
            header = ["Dimension", "Score", "Max", "Pct", "Weight"]
            rows_s: list[list[str]] = [header]
            for dim in score.dimensions:
                pct = dim.score / dim.max_score * 100 if dim.max_score > 0 else 0
                rows_s.append(
                    [
                        dim.name,
                        str(dim.score),
                        str(dim.max_score),
                        f"{pct:.0f}%",
                        f"{dim.weight}",
                    ]
                )
            table_s = Table().create_table(
                columns=len(header),
                rows=len(rows_s),
                text=[cell for row in rows_s for cell in row],
                text_align=["left", "right", "right", "right", "right"],
            )
            parts.append(table_s)
            parts.append(
                f"Overall: **{score.total}/{score.max_total}** ({score.weighted_score:.0%})"
            )
            if score.reasoning:
                parts.append(f"\n> {score.reasoning}")
            parts.append("")

    # Iteration breakdown (when --aitest-iterations produced multiple runs)
    if result.iterations:
        parts.append("**Iterations:**")
        parts.append("")
        header = ["#", "Result", "Duration", "Tokens", "Cost"]
        rows: list[list[str]] = [header]
        for it in result.iterations:
            icon = "✅" if it.passed else "❌"
            rows.append(
                [
                    str(it.iteration),
                    icon,
                    f"{it.duration_s:.1f}s",
                    f"{it.tokens:,}",
                    format_cost(it.cost),
                ]
            )
        table = Table().create_table(
            columns=len(header),
            rows=len(rows),
            text=[cell for row in rows for cell in row],
            text_align=["center", "center", "right", "right", "right"],
        )
        parts.append(table)
        parts.append("")

    # Tool calls
    if result.tool_calls:
        parts.append(_tool_calls_table(result.tool_calls))
        parts.append("")

    # Error
    if result.error:
        parts.append(f"**Error:** `{result.error}`")
        parts.append("")

    # Final response
    if result.final_response:
        parts.append("**Response:**")
        parts.append("")
        # Escape multiline responses for blockquote
        response_text = result.final_response[:500]
        for line in response_text.split("\n"):
            parts.append(f"> {line}")
        parts.append("")

    # Mermaid diagram
    if result.mermaid:
        parts.append("```mermaid")
        parts.append(result.mermaid)
        parts.append("```")
        parts.append("")

    parts.append("</details>")
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Test entry
# ---------------------------------------------------------------------------


def _test_status_icon(test: TestData) -> str:
    """Get the overall status icon for a test across all agents."""
    outcomes = [r.outcome for r in test.results_by_agent.values()]
    if all(o == "passed" for o in outcomes):
        return "✅"
    if any(o == "failed" for o in outcomes):
        return "❌"
    return "⏭️"


def _test_entry(
    test: TestData,
    agents_by_id: dict[str, AgentData],
    *,
    multi_agent: bool,
) -> str:
    """Render a single test with all agent results."""
    parts: list[str] = []

    status = _test_status_icon(test)
    diff = " ⚡" if test.has_difference and multi_agent else ""
    parts.append(Header.atx(level=_H4, title=f"{status} {test.display_name}{diff}"))

    for agent_id, result in test.results_by_agent.items():
        agent = agents_by_id.get(agent_id)
        agent_label = agent.name if agent else agent_id
        parts.append(_test_result_detail(result, agent_label, multi_agent=multi_agent))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Test group (session or standalone)
# ---------------------------------------------------------------------------


def _test_group(
    group: TestGroupData,
    agents_by_id: dict[str, AgentData],
    *,
    multi_agent: bool,
) -> str:
    """Render a test group (session or standalone)."""
    parts: list[str] = []

    if group.type == "session":
        parts.append(Header.atx(level=_H3, title=f"Session: {group.name}"))
    else:
        parts.append(Header.atx(level=_H3, title=group.name))

    for test in group.tests:
        parts.append(_test_entry(test, agents_by_id, multi_agent=multi_agent))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def _footer(timestamp: str) -> str:
    """Render the report footer."""
    return (
        f"*Generated by [pytest-aitest](https://github.com/sbroenne/pytest-aitest) "
        f"on {timestamp}*\n"
    )


# ---------------------------------------------------------------------------
# Full report composition
# ---------------------------------------------------------------------------


def render_markdown_report(ctx: ReportContext) -> str:
    """Render a complete Markdown report from a ReportContext.

    This is the top-level composition function, equivalent to
    full_report() for HTML. Each section is a typed component function
    that accepts dataclasses and returns a string.

    Args:
        ctx: The complete report context with all typed data.

    Returns:
        A complete GFM-compatible Markdown string.
    """
    multi_agent = len(ctx.agents) > 1
    sections: list[str] = []

    # 1. Header with metadata
    sections.append(_report_header(ctx.report))

    # 2. Agent leaderboard (table for multi, card for single)
    sections.append(_agent_leaderboard(ctx.agents))

    # 3. AI analysis
    if ctx.insights:
        sections.append(_ai_insights(ctx.insights.markdown_summary))

    # 4. Test results
    sections.append(Header.atx(level=_H2, title="Test Results"))
    for group in ctx.test_groups:
        sections.append(_test_group(group, ctx.agents_by_id, multi_agent=multi_agent))

    # 5. Footer
    sections.append(_footer(ctx.report.timestamp))

    return "\n".join(sections)
