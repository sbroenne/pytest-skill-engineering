"""Report generation with htpy components."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_aitest.core.serialization import serialize_dataclass
from pytest_aitest.reporting.components import full_report
from pytest_aitest.reporting.components.types import (
    AgentData,
    AgentStats,
    AIInsightsData,
    AssertionData,
    ReportContext,
    ReportMetadata,
    TestData,
    TestGroupData,
    TestResultData,
    ToolCallData,
)

if TYPE_CHECKING:
    from pytest_aitest.core.result import AgentResult
    from pytest_aitest.reporting.collector import SuiteReport, TestReport
    from pytest_aitest.reporting.insights import InsightsResult


def _sanitize_mermaid_text(text: str, limit: int) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    cleaned = cleaned.replace('"', "'")
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


def _resolve_agent_id(test: TestReport) -> str:
    """Get the agent ID from TestReport."""
    agent_id = test.agent_id
    if not agent_id:
        msg = f"Test {test.name!r} missing 'agent_id'"
        raise ValueError(msg)
    return agent_id


def generate_html(
    report: SuiteReport,
    output_path: str | Path,
    *,
    insights: InsightsResult | None = None,
    min_pass_rate: int | None = None,
) -> None:
    """Generate HTML report from test results and AI insights.

    Args:
        report: Test suite report data (dataclass)
        output_path: Path to write HTML file
        insights: InsightsResult from AI analysis (if None, no insights shown)
        min_pass_rate: Minimum pass rate threshold for disqualifying agents

    Example:
        generate_html(suite_report, "report.html")
    """
    context = _build_report_context(report, insights=insights, min_pass_rate=min_pass_rate)
    html_node = full_report(context)
    html_str = str(html_node)
    Path(output_path).write_text(html_str, encoding="utf-8")


def generate_json(
    report: SuiteReport,
    output_path: str | Path,
    *,
    insights: InsightsResult | None = None,
) -> None:
    """Generate JSON report from dataclass.

    Args:
        report: Test suite report data
        output_path: Path to write JSON file
        insights: InsightsResult from AI analysis
    """
    import json

    report_dict = serialize_dataclass(report)
    report_dict["schema_version"] = "3.0"

    if insights:
        report_dict["insights"] = {
            "markdown_summary": insights.markdown_summary,
            "cost_usd": insights.cost_usd,
            "tokens_used": insights.tokens_used,
            "cached": insights.cached,
        }

    json_str = json.dumps(report_dict, indent=2, default=str)
    Path(output_path).write_text(json_str, encoding="utf-8")


def generate_mermaid_sequence(result: AgentResult) -> str:
    """Generate Mermaid sequence diagram from agent result.

    Example output:
        sequenceDiagram
            participant User
            participant Agent
            participant Tools

            User->>Agent: Hello!
            Agent->>Tools: read_file(path="/tmp/test.txt")
            Tools-->>Agent: File contents...
            Agent->>User: Here is the file...
    """
    lines = [
        "sequenceDiagram",
        "    participant User",
        "    participant Agent",
        "    participant Tools",
        "",
    ]

    for turn in result.turns:
        if turn.role == "user":
            content = _sanitize_mermaid_text(turn.content, 80)
            lines.append(f'    User->>Agent: "{content}"')

        elif turn.role == "assistant":
            if turn.tool_calls:
                for tc in turn.tool_calls:
                    args_preview = _sanitize_mermaid_text(str(tc.arguments), 60)
                    lines.append(f'    Agent->>Tools: "{tc.name}({args_preview})"')
                    if tc.error:
                        err_preview = _sanitize_mermaid_text(str(tc.error), 60)
                        lines.append(f'    Tools--xAgent: "Error: {err_preview}"')
                    elif tc.result:
                        result_preview = _sanitize_mermaid_text(tc.result, 60)
                        lines.append(f'    Tools-->>Agent: "{result_preview}"')
            else:
                content = _sanitize_mermaid_text(turn.content, 80)
                lines.append(f'    Agent->>User: "{content}"')

    return "\n".join(lines)


# --- Internal helpers ---


def _build_report_context(
    report: SuiteReport,
    *,
    insights: InsightsResult | None = None,
    min_pass_rate: int | None = None,
) -> ReportContext:
    """Build typed ReportContext from SuiteReport."""
    ts = report.timestamp
    if isinstance(ts, datetime):
        timestamp_str = ts.strftime("%B %d, %Y at %I:%M %p")
    else:
        try:
            dt = datetime.fromisoformat(str(ts))
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            timestamp_str = dt.strftime("%B %d, %Y at %I:%M %p")
        except Exception:
            timestamp_str = str(ts)

    analysis_cost = insights.cost_usd if insights else None

    token_stats = report.token_stats
    token_min = token_stats.get("min", 0)
    token_max = token_stats.get("max", 0)

    report_meta = ReportMetadata(
        name=report.name,
        timestamp=timestamp_str,
        passed=report.passed,
        failed=report.failed,
        total=report.total,
        duration_ms=report.duration_ms or 0,
        total_cost_usd=report.total_cost_usd or 0,
        suite_docstring=getattr(report, "suite_docstring", None),
        analysis_cost_usd=analysis_cost,
        test_files=report.test_files,
        token_min=token_min,
        token_max=token_max,
    )

    agents, agents_by_id = _build_agents(report, min_pass_rate=min_pass_rate)
    all_agent_ids = [a.id for a in agents]

    agents_by_coverage = sorted(
        agents, key=lambda a: (-a.total, a.disqualified, -a.pass_rate, a.cost)
    )
    selected_agent_ids = [a.id for a in agents_by_coverage[:2]]

    test_groups = _build_test_groups_typed(report, all_agent_ids, agents_by_id)

    insights_data = None
    if insights and insights.markdown_summary:
        insights_data = AIInsightsData(markdown_summary=insights.markdown_summary)

    return ReportContext(
        report=report_meta,
        agents=agents,
        agents_by_id=agents_by_id,
        all_agent_ids=all_agent_ids,
        selected_agent_ids=selected_agent_ids,
        test_groups=test_groups,
        total_tests=len(report.tests),
        insights=insights_data,
    )


def _build_agents(
    report: SuiteReport, *, min_pass_rate: int | None = None
) -> tuple[list[AgentData], dict[str, AgentData]]:
    """Build agent data from test results."""
    agent_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "cost": 0.0,
            "tokens": 0,
            "duration_ms": 0,
            "agent_name": None,
            "skill": None,
            "system_prompt_name": None,
            "model": None,
        }
    )

    for test in report.tests:
        agent_id = _resolve_agent_id(test)

        model = test.model or "unknown"
        agent_name = test.agent_name or model
        skill = test.skill_name
        system_prompt_name = test.system_prompt_name

        stats = agent_stats[agent_id]
        stats["model"] = model
        stats["agent_name"] = agent_name
        stats["skill"] = skill
        stats["system_prompt_name"] = system_prompt_name
        stats["total"] += 1

        if test.outcome == "passed":
            stats["passed"] += 1
        else:
            stats["failed"] += 1

        if test.duration_ms:
            stats["duration_ms"] += test.duration_ms

        if test.agent_result:
            if test.agent_result.cost_usd:
                stats["cost"] += test.agent_result.cost_usd
            if test.agent_result.token_usage:
                usage = test.agent_result.token_usage
                stats["tokens"] += usage.get("prompt", 0) + usage.get("completion", 0)

    agents = []
    for agent_id, stats in agent_stats.items():
        total = stats["total"]
        passed = stats["passed"]
        pass_rate = (passed / total * 100) if total > 0 else 0

        disqualified = min_pass_rate is not None and pass_rate < min_pass_rate

        agents.append(
            AgentData(
                id=agent_id,
                name=stats["agent_name"],
                skill=stats["skill"],
                system_prompt_name=stats["system_prompt_name"],
                passed=passed,
                failed=stats["failed"],
                total=total,
                pass_rate=pass_rate,
                cost=stats["cost"],
                tokens=stats["tokens"],
                duration_s=stats["duration_ms"] / 1000,
                disqualified=disqualified,
            )
        )

    agents.sort(key=lambda a: (a.disqualified, -a.pass_rate, a.cost))

    for i, agent in enumerate(agents):
        if not agent.disqualified:
            agents[i] = AgentData(
                id=agent.id,
                name=agent.name,
                skill=agent.skill,
                system_prompt_name=agent.system_prompt_name,
                passed=agent.passed,
                failed=agent.failed,
                total=agent.total,
                pass_rate=agent.pass_rate,
                cost=agent.cost,
                tokens=agent.tokens,
                duration_s=agent.duration_s,
                is_winner=True,
            )
            break

    agents_by_id = {a.id: a for a in agents}
    return agents, agents_by_id


def _build_test_groups_typed(
    report: SuiteReport,
    all_agent_ids: list[str],
    agents_by_id: dict[str, AgentData],
) -> list[TestGroupData]:
    """Build typed test groups for htpy components."""
    test_groups: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))

    for test in report.tests:
        parts = test.name.split("::")
        if len(parts) >= 2:
            class_name = parts[-2]
            test_name = parts[-1].split("[")[0]
        else:
            class_name = "standalone"
            test_name = parts[-1].split("[")[0]

        test_groups[class_name][test_name].append(test)

    result = []
    for group_name, tests_by_name in test_groups.items():
        is_session = group_name.startswith("Test") and len(tests_by_name) > 1

        test_list = []
        for test_name, test_variants in tests_by_name.items():
            results_by_agent: dict[str, TestResultData] = {}
            has_difference = False
            has_failed = False
            outcomes = set()
            first_test = test_variants[0] if test_variants else None

            for test in test_variants:
                agent_id = _resolve_agent_id(test)

                if agent_id in all_agent_ids:
                    outcome = test.outcome or "unknown"
                    outcomes.add(outcome)

                    if outcome != "passed":
                        has_failed = True

                    tool_calls = []
                    if test.agent_result and test.agent_result.turns:
                        for turn in test.agent_result.turns:
                            if turn.tool_calls:
                                for tc in turn.tool_calls:
                                    tool_calls.append(
                                        ToolCallData(
                                            name=tc.name,
                                            success=tc.error is None,
                                            error=tc.error,
                                            args=tc.arguments,
                                            result=tc.result,
                                        )
                                    )

                    assertions_data = []
                    if test.assertions:
                        for a in test.assertions:
                            if hasattr(a, "type"):
                                assertions_data.append(
                                    AssertionData(
                                        type=a.type,
                                        passed=a.passed,
                                        message=a.message or "",
                                        details=a.details,
                                    )
                                )
                            else:
                                assertions_data.append(
                                    AssertionData(
                                        type=a.get("type", "unknown"),
                                        passed=a.get("passed", True),
                                        message=a.get("message", ""),
                                        details=a.get("details"),
                                    )
                                )

                    duration_ms = test.duration_ms or 0
                    has_result = test.agent_result and test.agent_result.turns
                    turn_count = len(test.agent_result.turns) if has_result else 0
                    tokens = 0
                    if test.agent_result and test.agent_result.token_usage:
                        usage = test.agent_result.token_usage
                        tokens = usage.get("prompt", 0) + usage.get("completion", 0)

                    agent_result = test.agent_result
                    mermaid = generate_mermaid_sequence(agent_result) if agent_result else None
                    final_resp = agent_result.final_response if agent_result else None
                    results_by_agent[agent_id] = TestResultData(
                        outcome=outcome,
                        passed=outcome == "passed",
                        duration_s=duration_ms / 1000,
                        tokens=tokens,
                        cost=agent_result.cost_usd if agent_result else 0,
                        tool_calls=tool_calls,
                        tool_count=len(tool_calls),
                        turns=turn_count,
                        mermaid=mermaid,
                        final_response=final_resp,
                        error=test.error,
                        assertions=assertions_data,
                    )

            if len(outcomes) > 1:
                has_difference = True

            display_name = test_name
            if first_test and hasattr(first_test, "docstring") and first_test.docstring:
                first_line = first_test.docstring.split("\n")[0].strip()
                if first_line:
                    display_name = first_line[:60] + ("…" if len(first_line) > 60 else "")

            test_list.append(
                TestData(
                    id=test_name,
                    display_name=display_name,
                    results_by_agent=results_by_agent,
                    has_difference=has_difference,
                    has_failed=has_failed,
                )
            )

        agent_stats_map: dict[str, AgentStats] = {}
        for agent_id in all_agent_ids:
            passed = sum(
                1
                for t in test_list
                if t.results_by_agent.get(agent_id)
                and t.results_by_agent[agent_id].outcome == "passed"
            )
            failed = sum(
                1
                for t in test_list
                if t.results_by_agent.get(agent_id)
                and t.results_by_agent[agent_id].outcome != "passed"
            )
            agent_stats_map[agent_id] = AgentStats(passed=passed, failed=failed)

        result.append(
            TestGroupData(
                type="session" if is_session else "standalone",
                name=group_name,
                tests=test_list,
                agent_stats=agent_stats_map,
            )
        )

    return result
