"""Full report component - main HTML page."""

from __future__ import annotations

import importlib.resources as resources
import json
from typing import TYPE_CHECKING

from htpy import (
    Node,
    body,
    button,
    div,
    h1,
    h2,
    head,
    header,
    html,
    link,
    meta,
    script,
    section,
    span,
    style,
    title,
)
from markupsafe import Markup

from .agent_leaderboard import agent_leaderboard, format_cost
from .agent_selector import agent_selector
from .overlay import overlay
from .test_grid import test_grid
from .types import AgentData, AIInsightsData, ReportContext, ReportMetadata

if TYPE_CHECKING:
    pass


def _load_static_asset(path: str) -> str:
    """Load a static asset from the templates directory."""
    templates = resources.files("pytest_skill_engineering").joinpath("templates")
    parts = path.split("/")
    current = templates
    for part in parts:
        current = current.joinpath(part)
    return current.read_text(encoding="utf-8")


def _html_head(report: ReportMetadata) -> Node:
    """Render the HTML head section."""
    css_content = _load_static_asset("partials/report.css")

    return head[
        meta(charset="UTF-8"),
        meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        title[f"{report.name} - Test Report"],
        link(rel="preconnect", href="https://fonts.googleapis.com"),
        link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=True),
        link(
            href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;600;700&family=Roboto+Mono&display=swap",
            rel="stylesheet",
        ),
        script(src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"),
        style[Markup(css_content)],
    ]


def _status_badge(report: ReportMetadata) -> Node | None:
    """Render the pass/fail status badge."""
    if report.failed == 0 and report.passed > 0:
        return div(".status-passed")[span["✓"], span["All Passed"]]
    if report.failed > 0:
        return div(".status-failed")[span["✗"], span[f"{report.failed} Failed"]]
    return None


def _pricing_badge(report: ReportMetadata) -> Node | None:
    """Render a warning badge when models lack pricing data."""
    if not report.models_without_pricing:
        return None
    models = ", ".join(report.models_without_pricing)
    count = len(report.models_without_pricing)
    label = f"{count} Model{'' if count == 1 else 's'} Missing Pricing"
    return div(".status-warning", title=f"No pricing data for: {models}")[span["⚠"], span[label]]


def _report_header(report: ReportMetadata) -> Node:
    """Render the report header section."""
    display_title = report.suite_docstring or report.name or "Test Report"
    duration_s = report.duration_ms / 1000

    # Calculate test run cost (total minus analysis)
    test_run_cost = report.total_cost_usd
    if report.analysis_cost_usd:
        test_run_cost -= report.analysis_cost_usd
    test_run_cost = max(test_run_cost, 0.0)

    # Create test file links
    file_links = []
    for test_file in report.test_files:
        # Use just the filename for display, full path for link
        display_name = test_file.split("/")[-1]
        file_links.append(
            span[
                "📄 ",
                span(".text-text-light.hover:text-blue-400.cursor-pointer", title=test_file)[
                    display_name
                ],
            ]
        )

    # Build cost breakdown
    cost_parts = []
    cost_parts.append(
        span(".tabular-nums", title="Test execution cost")[f"🧪 {format_cost(test_run_cost)}"]
    )
    if report.analysis_cost_usd:
        cost_parts.append(
            span(".tabular-nums", title="AI analysis cost")[
                f"🤖 {format_cost(report.analysis_cost_usd)}"
            ]
        )
    cost_parts.append(
        span(".tabular-nums.font-semibold", title="Total cost")[
            f"💰 {format_cost(report.total_cost_usd)}"
        ]
    )

    # Token range display
    token_range_node = None
    if report.token_min > 0 or report.token_max > 0:
        if report.token_min == report.token_max:
            token_range_node = span(".tabular-nums", title="Tokens per test")[
                f"{report.token_min:,} tok"
            ]
        else:
            token_range_node = span(".tabular-nums", title="Token range (min-max per test)")[
                f"{report.token_min:,}–{report.token_max:,} tok"
            ]

    header_items = [
        span(".opacity-70")[report.timestamp],
        *file_links,
        span(".tabular-nums")[f"{report.total} tests"],
        span(".tabular-nums")[f"{duration_s:.1f}s"],
    ]

    if token_range_node:
        header_items.append(token_range_node)

    header_items.extend(cost_parts)

    return header(".report-header.mb-8")[
        div(".flex.justify-between.items-start.gap-4.mb-4")[
            div(".flex-1")[h1(".text-2xl.font-medium.mb-1")[display_title],],
            div(".flex.gap-2.items-start")[
                _pricing_badge(report),
                _status_badge(report),
            ],
        ],
        div(".flex.flex-wrap.gap-x-6.gap-y-1.py-3.border-t.border-white/10.text-sm")[*header_items],
    ]


def _render_markdown(text: str) -> Markup:
    """Convert markdown to HTML.

    Mermaid fenced code blocks (```mermaid) are converted to
    ``<pre class="mermaid">`` so that Mermaid.js renders them as diagrams.
    """
    import re

    try:
        import markdown

        html_text = markdown.markdown(text, extensions=["extra"])
        # Convert <pre><code class="language-mermaid">…</code></pre> to
        # <pre class="mermaid">…</pre> so Mermaid.js picks them up.
        html_text = re.sub(
            r'<pre><code class="language-mermaid">(.*?)</code></pre>',
            r'<pre class="mermaid">\1</pre>',
            html_text,
            flags=re.DOTALL,
        )
        return Markup(html_text)
    except ImportError:
        import html as html_module

        escaped = html_module.escape(text)
        return Markup(escaped.replace("\n", "<br>"))


def _ai_insights_section(insights: AIInsightsData) -> Node | None:
    """Render the AI insights section."""
    if not insights.markdown_summary:
        return None

    return section(".mb-8")[
        div(".ai-insights")[
            div(".ai-insights-header")[
                span["🤖"],
                span["AI Analysis"],
                button(
                    class_="ml-auto text-text-muted hover:text-text-light text-sm",
                    onclick="this.closest('.ai-insights').querySelector('.card-body').classList.toggle('hidden')",
                )["Toggle"],
            ],
            div(".card-body")[
                div(".markdown-content")[_render_markdown(insights.markdown_summary)],
            ],
        ],
    ]


def _agent_leaderboard_section(agents: list[AgentData]) -> Node | None:
    """Render the agent leaderboard section."""
    if not agents or len(agents) <= 1:
        return None

    leaderboard = agent_leaderboard(agents)
    if not leaderboard:
        return None

    return section(".mb-8")[
        h2(".section-title")["🏆 Eval Leaderboard"],
        leaderboard,
    ]


def _agent_selector_section(agents: list[AgentData], selected_ids: list[str]) -> Node | None:
    """Render the agent selector section."""
    selector = agent_selector(agents, selected_ids)
    if not selector:
        return None

    return section(".mb-8")[selector]


def _test_results_section(ctx: ReportContext) -> Node:
    """Render the test results section."""
    return section(".mb-8")[
        h2(".section-title")["📋 Test Results"],
        test_grid(
            ctx.test_groups,
            ctx.all_agent_ids,
            ctx.selected_agent_ids,
            ctx.agents_by_id,
            ctx.total_tests,
        ),
    ]


def _scripts_section(ctx: ReportContext) -> Node:
    """Render the scripts section with all JS."""
    js_content = _load_static_asset("partials/scripts.js")

    # Serialize agent data for client-side filtering
    agents_json = json.dumps(
        [
            {
                "id": a.id,
                "name": a.name,
                "pass_rate": a.pass_rate,
            }
            for a in ctx.agents
        ]
    )

    agents_by_id_json = json.dumps({a.id: {"id": a.id, "name": a.name} for a in ctx.agents})

    selected_ids_json = json.dumps(ctx.selected_agent_ids)

    # Client-side JS for agent comparison
    client_js = f"""
{js_content}

// All agent data for client-side filtering
const allAgents = {agents_json};
const allAgentsById = {agents_by_id_json};

// Track selected agents (exactly 2)
let selectedAgentIds = {selected_ids_json};

// Eval comparison logic - always keep exactly 2 selected
function updateAgentComparison(clickedAgentId) {{
    const checkboxes = document.querySelectorAll('input[name="compare-agent"]');
    
    // If clicking an already-selected agent, do nothing (keep 2 selected)
    if (selectedAgentIds.includes(clickedAgentId)) {{
        // Re-check it to prevent unchecking
        checkboxes.forEach(cb => {{
            if (cb.value === clickedAgentId) {{
                cb.checked = true;
            }}
        }});
        return;
    }}
    
    // Replace the oldest selection with the new one
    selectedAgentIds.shift();  // Remove first (oldest)
    selectedAgentIds.push(clickedAgentId);  // Add new one
    
    // Update all checkboxes to match selectedAgentIds
    checkboxes.forEach(cb => {{
        cb.checked = selectedAgentIds.includes(cb.value);
        cb.closest('.agent-chip').classList.toggle('selected', cb.checked);
    }});
    
    // Update visible columns in test comparison
    document.querySelectorAll('.comparison-column').forEach(col => {{
        const agentId = col.dataset.agentId;
        if (agentId) {{
            const shouldShow = selectedAgentIds.includes(agentId);
            col.classList.toggle('hidden', !shouldShow);
            
            // Render mermaid diagrams in newly visible columns
            if (shouldShow) {{
                const diagrams = col.querySelectorAll('.mermaid:not([data-processed])');
                if (diagrams.length > 0) {{
                    mermaid.run({{ nodes: diagrams }});
                }}
            }}
        }}
    }});
    
    // Update comparison grid layout based on visible columns
    document.querySelectorAll('.comparison-grid').forEach(grid => {{
        const visibleCols = grid.querySelectorAll('.comparison-column:not(.hidden)').length;
        grid.style.gridTemplateColumns = `repeat(${{visibleCols}}, 1fr)`;
    }});
    
    // Update agent cards visibility
    document.querySelectorAll('.agent-card[data-card-id]').forEach(card => {{
        const agentId = card.dataset.cardId;
        card.classList.toggle('hidden', !selectedAgentIds.includes(agentId));
    }});
    
    // Update comparison row agent results
    document.querySelectorAll('.agent-result-item').forEach(item => {{
        const agentId = item.dataset.agentId;
        item.classList.toggle('hidden', !selectedAgentIds.includes(agentId));
    }});
    
    console.log('Selected agents:', selectedAgentIds);
}}

// Test filtering
function filterTests(filter) {{
    document.querySelectorAll('.filter-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.dataset.filter === filter);
    }});
    
    let visibleCount = 0;
    document.querySelectorAll('.test-row').forEach(row => {{
        let show = true;
        if (filter === 'diff') {{
            show = row.dataset.hasDiff === 'true';
        }} else if (filter === 'failed') {{
            show = row.dataset.hasFailed === 'true';
        }}
        row.classList.toggle('hidden', !show);
        if (show) visibleCount++;
    }});
    
    document.getElementById('visible-count').textContent = visibleCount;
}}

// Group toggle
function toggleGroup(group) {{
    group.classList.toggle('collapsed');
}}

// Test detail toggle - also renders mermaid diagrams when expanded
function toggleTestDetail(row) {{
    const detail = row.querySelector('.test-detail');
    const wasHidden = detail.classList.contains('hidden');
    detail.classList.toggle('hidden');
    
    // If we're showing the detail, render any mermaid diagrams
    if (wasHidden) {{
        const diagrams = detail.querySelectorAll('.mermaid:not([data-processed])');
        if (diagrams.length > 0) {{
            mermaid.run({{ nodes: diagrams }});
        }}
    }}
}}

// Initialize on page load - process visible mermaid diagrams
document.addEventListener('DOMContentLoaded', () => {{
    // Mermaid should auto-process with startOnLoad, but just in case
    const visibleDiagrams = document.querySelectorAll('.mermaid:not(.hidden .mermaid)');
    if (visibleDiagrams.length > 0) {{
        mermaid.run({{ nodes: visibleDiagrams }});
    }}
}});
"""

    # Wrap in Markup so htpy doesn't HTML-escape the JavaScript
    return script[Markup(client_js)]


def full_report(ctx: ReportContext) -> Node:
    """Render the complete HTML report.

    Args:
        ctx: Complete report context with all data.

    Returns:
        htpy Node for the full HTML document.
    """
    return html(lang="en", class_="dark")[
        _html_head(ctx.report),
        body(".bg-surface.text-text.min-h-screen")[
            div(".max-w-6xl.mx-auto.px-6.py-8")[
                _report_header(ctx.report),
                _ai_insights_section(ctx.insights),
                _agent_leaderboard_section(ctx.agents),
                _agent_selector_section(ctx.agents, ctx.selected_agent_ids),
                _test_results_section(ctx),
            ],
            overlay(),
            _scripts_section(ctx),
        ],
    ]
