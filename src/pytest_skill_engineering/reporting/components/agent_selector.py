"""Agent selector component - toggle chips for agent comparison."""

from __future__ import annotations

# Note: htpy uses `input` not `input_` - no underscore suffix needed
from htpy import Node, div, input, label, span

from .types import AgentData


def _agent_chip(agent: AgentData, is_selected: bool) -> Node:
    """Render a single agent selection chip."""
    selected_class = "selected" if is_selected else ""
    checked = "checked" if is_selected else None

    return label(class_=f"agent-chip {selected_class}")[
        input(
            type="checkbox",
            name="compare-agent",
            value=agent.id,
            checked=checked,
            class_="sr-only",
            onchange=f"updateAgentComparison('{agent.id}')",
        ),
        span(".truncate")[agent.name],
        span(".text-xs.text-text-muted.tabular-nums")[f"{agent.pass_rate:.0f}%"],
    ]


def agent_selector(
    agents: list[AgentData],
    selected_agent_ids: list[str],
) -> Node | None:
    """Render the agent selector for comparison mode.

    Only shown when there are more than 2 agents.

    Args:
        agents: All agents.
        selected_agent_ids: IDs of currently selected agents (exactly 2).

    Returns:
        htpy Node or None if 2 or fewer agents.
    """
    if len(agents) <= 2:
        return None

    selected_set = set(selected_agent_ids)

    return div(".card.p-4")[
        div(".flex.items-center.gap-3.mb-3")[
            span(".text-sm.text-text-muted")["Compare:"],
            span(".text-xs.text-text-muted.opacity-70")["(Click to swap agents)"],
        ],
        div(".flex.flex-wrap.gap-2")[
            [_agent_chip(agent, agent.id in selected_set) for agent in agents]
        ],
    ]
