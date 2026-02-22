"""Test comparison component - side-by-side expanded view for a single test."""

from __future__ import annotations

import base64

from htpy import Node, button, code, div, img, span

from .agent_leaderboard import format_cost
from .types import AgentData, AssertionData, TestData, TestResultData, ToolCallData


def _metric_cell(value: str, label: str) -> Node:
    """Render a single metric cell."""
    return div[
        div(".text-sm.font-medium.text-text-light.tabular-nums")[value],
        div(".text-xs.text-text-muted")[label],
    ]


def _metrics_row(result: TestResultData) -> Node:
    """Render the metrics row for a test result (2 rows of metrics)."""
    cost_cells: list[Node] = [_metric_cell(format_cost(result.cost), "cost")]

    # Iteration stats when aggregated across multiple runs
    if result.iterations and result.iteration_pass_rate is not None:
        n = len(result.iterations)
        n_passed = sum(1 for it in result.iterations if it.passed)
        cost_cells.append(
            _metric_cell(f"{n_passed}/{n}", "iterations passed"),
        )
        cost_cells.append(
            _metric_cell(f"{result.iteration_pass_rate:.0f}%", "iter pass rate"),
        )

    return div(".space-y-2.mb-4")[
        # First row: duration, turns, tools
        div(".grid.grid-cols-4.gap-2.p-3.bg-surface-elevated.rounded-material.text-center")[
            _metric_cell(f"{result.duration_s:.2f}s", "duration"),
            _metric_cell(str(result.turns), "turns"),
            _metric_cell(str(result.tool_count), "tools"),
            _metric_cell(f"{result.tokens:,}", "tokens"),
        ],
        # Second row: cost + iterations
        div(".grid.grid-cols-4.gap-2.p-3.bg-surface-elevated.rounded-material.text-center")[
            *cost_cells,
        ],
    ]


def _mermaid_diagram(result: TestResultData) -> Node | None:
    """Render a button that opens the sequence diagram in fullscreen overlay."""
    if not result.mermaid:
        return None

    btn_cls = (
        "inline-flex items-center gap-2 px-3 py-1.5 text-sm "
        "bg-surface-code rounded-material border border-white/10 "
        "cursor-pointer hover:border-primary/30 hover:bg-primary/5 transition-colors "
        "text-text-muted hover:text-text-light"
    )
    return div(".mb-4")[
        button(
            class_=btn_cls,
            onclick="event.stopPropagation(); showDiagram(this.dataset.mermaidCode);",
            data_mermaid_code=result.mermaid,
        )[span["📊"], span["View Sequence Diagram"]],
    ]


def _tool_call_item(tc: ToolCallData) -> Node:
    """Render a single tool call."""
    bg_class = "bg-green-500/5" if tc.success else "bg-red-500/5"
    status_class = "text-green-400" if tc.success else "text-red-400"
    status_icon = "✅" if tc.success else "❌"

    error_node = None
    if tc.error:
        display_error = tc.error[:40] + ("..." if len(tc.error) > 40 else "")
        error_node = span(".text-xs.text-red-400.truncate", title=tc.error)[display_error]

    # Image thumbnail for tools that returned images
    image_node = None
    if tc.image_content and tc.image_media_type:
        b64 = base64.b64encode(tc.image_content).decode("ascii")
        data_uri = f"data:{tc.image_media_type};base64,{b64}"
        image_node = img(
            src=data_uri,
            alt="Tool result image",
            style="max-width: 200px; max-height: 150px; border-radius: 4px; margin-top: 4px;",
            class_="cursor-pointer",
        )

    call_row = div(class_=f"flex items-center gap-2 text-sm p-2 rounded {bg_class}")[
        span(class_=status_class)[status_icon],
        code(".tool-name")[tc.name],
        error_node,
    ]

    if image_node:
        return div[call_row, div(".pl-8.pb-1")[image_node]]

    return call_row


def _tool_calls_section(result: TestResultData) -> Node | None:
    """Render the tool calls section."""
    if not result.tool_calls:
        return None

    return div(".mb-4")[
        div(".text-sm.font-medium.text-text-light.mb-3.flex.items-center.gap-2")[
            span["🔧"],
            span["Tool Calls"],
        ],
        div(".space-y-1")[[_tool_call_item(tc) for tc in result.tool_calls]],
    ]


def _assertion_item(a: AssertionData) -> Node:
    """Render a single assertion."""
    bg_class = "bg-green-500/5" if a.passed else "bg-red-500/5"
    status_class = "text-green-400" if a.passed else "text-red-400"
    status_icon = "✅" if a.passed else "❌"

    return div(class_=f"flex items-center gap-2 text-sm p-2 rounded {bg_class}")[
        span(class_=status_class)[status_icon],
        code(".text-text-muted")[a.type],
        span(".text-text")[a.message],
    ]


def _assertions_section(result: TestResultData) -> Node | None:
    """Render the assertions section."""
    if not result.assertions:
        return None

    return div(".mb-4")[
        div(".text-sm.font-medium.text-text-light.mb-3.flex.items-center.gap-2")[
            span["✓"],
            span["Assertions"],
        ],
        div(".space-y-2")[[_assertion_item(a) for a in result.assertions]],
    ]


def _scores_section(result: TestResultData) -> Node | None:
    """Render the LLM scores section with dimension bars."""
    if not result.scores:
        return None

    all_dims: list[Node] = []
    for score in result.scores:
        dim_items: list[Node] = []
        for dim in score.dimensions:
            pct = dim.score / dim.max_score * 100 if dim.max_score > 0 else 0
            # Color gradient: green for high, yellow for mid, red for low
            if pct >= 70:
                fill_color = "var(--color-green)"
            elif pct >= 40:
                fill_color = "var(--color-yellow, #facc15)"
            else:
                fill_color = "var(--color-red)"

            weight_label = f" (w={dim.weight})" if dim.weight != 1.0 else ""

            dim_items.append(
                div(".score-dimension.mb-2")[
                    div(".flex.items-center.justify-between.text-xs.mb-1")[
                        span(".text-text-light")[f"{dim.name}{weight_label}"],
                        span(".text-text-muted.tabular-nums")[f"{dim.score}/{dim.max_score}"],
                    ],
                    div(".score-track")[
                        div(
                            ".score-fill",
                            style=f"width: {pct:.0f}%; background: {fill_color};",
                        ),
                    ],
                ]
            )

        # Overall score summary
        overall = div(
            ".flex.items-center.justify-between.p-2.bg-surface-elevated.rounded-material.mt-2.mb-3"
        )[
            span(".text-sm.text-text-light")["Overall"],
            span(".text-sm.font-medium.text-text.tabular-nums")[
                f"{score.total}/{score.max_total} ({score.weighted_score:.0%})"
            ],
        ]

        # Reasoning
        reasoning_node = None
        if score.reasoning:
            reasoning_node = div(
                ".text-xs.text-text-muted.p-2.bg-surface-code.rounded-material.mb-3",
                style="white-space: pre-wrap;",
            )[score.reasoning]

        all_dims.extend(dim_items)
        all_dims.append(overall)
        if reasoning_node:
            all_dims.append(reasoning_node)

    return div(".mb-4")[
        div(".text-sm.font-medium.text-text-light.mb-3.flex.items-center.gap-2")[
            span["📊"],
            span["Scores"],
        ],
        div[all_dims],
    ]


def _response_section(result: TestResultData) -> Node | None:
    """Render the final response section."""
    if not result.final_response:
        return None

    return div(".mb-4")[
        div(".text-sm.font-medium.text-text-light.mb-3.flex.items-center.gap-2")[
            span["💬"],
            span["Response"],
        ],
        div(
            style=(
                "padding: 1rem; background-color: var(--color-surface-elevated); "
                "border-radius: 0.5rem; color: var(--color-text); "
                "white-space: pre-wrap; word-wrap: break-word; line-height: 1.625;"
            )
        )[result.final_response],
    ]


def _error_section(result: TestResultData) -> Node | None:
    """Render the error section."""
    if not result.error:
        return None

    # Truncate very long error messages to first 500 chars + ellipsis
    error_text = result.error
    if len(error_text) > 500:
        error_text = error_text[:500] + "\n\n... (error truncated, see full logs for details)"

    return div[
        div(".text-sm.font-medium.text-red-400.mb-3.flex.items-center.gap-2")[
            span["❌"],
            span["Error"],
        ],
        div(
            style=(
                "padding: 0.75rem; background-color: rgb(127, 29, 29); "
                "border: 1px solid rgb(153, 27, 27); border-radius: 0.5rem; "
                "color: rgb(254, 202, 202); font-size: 0.875rem; "
                "white-space: pre-wrap; word-wrap: break-word; max-height: 200px; "
                "overflow-y: auto;"
            )
        )[error_text],
    ]


def _agent_result_column(
    agent: AgentData,
    result: TestResultData | None,
    is_selected: bool,
) -> Node:
    """Render a single agent's result column."""
    hidden_class = "hidden" if not is_selected else ""

    if result:
        passed_border = "border-l-[3px] border-green-500"
        failed_border = "border-l-[3px] border-red-500"
        border_class = passed_border if result.passed else failed_border
        status_text = "passed" if result.passed else "failed"
        status_class = (
            "bg-green-500/15 text-green-400" if result.passed else "bg-red-500/15 text-red-400"
        )
    else:
        border_class = "opacity-50"
        status_text = None

    status_span = None
    if status_text:
        status_span = span(class_=f"px-2 py-0.5 rounded text-xs font-medium {status_class}")[
            status_text
        ]

    no_result_div = div(".text-center.text-text-muted.py-8")["No result for this agent"]
    content = _result_content(result) if result else no_result_div

    return div(
        class_=f"comparison-column {hidden_class} {border_class}",
        data_agent_id=agent.id,
    )[
        # Eval name + status header
        div(".flex.items-center.justify-between.mb-4")[
            div(".font-medium.text-text-light")[agent.name],
            status_span,
        ],
        # Content
        content,
    ]


def _result_content(result: TestResultData) -> Node:
    """Render the full content for a result."""
    return [
        _metrics_row(result),
        _mermaid_diagram(result),
        _tool_calls_section(result),
        _assertions_section(result),
        _scores_section(result),
        _response_section(result),
        _error_section(result),
    ]


def test_comparison(
    test: TestData,
    all_agent_ids: list[str],
    selected_agent_ids: list[str],
    agents_by_id: dict[str, AgentData],
) -> Node:
    """Render the test comparison view.

    Shows side-by-side results for each agent on a single test.

    Args:
        test: Test data with results_by_agent.
        all_agent_ids: All agent IDs.
        selected_agent_ids: Currently selected agent IDs.
        agents_by_id: Mapping of agent ID to agent data.

    Returns:
        htpy Node for the comparison grid.
    """
    selected_set = set(selected_agent_ids)
    visible_count = len([agent_id for agent_id in all_agent_ids if agent_id in selected_set])
    if visible_count == 0:
        visible_count = 1

    return div(
        class_="comparison-grid grid gap-4 p-5",
        style=f"grid-template-columns: repeat({visible_count}, 1fr);",
    )[
        [
            _agent_result_column(
                agents_by_id[agent_id],
                test.results_by_agent.get(agent_id),
                agent_id in selected_set,
            )
            for agent_id in all_agent_ids
        ]
    ]
