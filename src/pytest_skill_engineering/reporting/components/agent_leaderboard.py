"""Eval leaderboard component - ranked table with medals."""

from __future__ import annotations

from htpy import Node, div, span, table, tbody, td, th, thead, tr

from .types import AgentData


def format_cost(cost: float, premium_requests: float = 0.0) -> str:
    """Format cost: premium requests for CopilotEval, USD for Eval."""
    if premium_requests > 0:
        return f"{premium_requests:.0f} PR"
    if cost == 0:
        return "N/A"
    if cost < 0.01:
        return f"${cost:.6f}"
    return f"${cost:.4f}"


def _pass_rate_class(rate: float) -> str:
    """Get CSS class based on pass rate."""
    if rate == 100:
        return "text-green-400"
    if rate >= 80:
        return "text-yellow-400"
    return "text-red-400"


def _medal(rank: int) -> str:
    """Get medal emoji for rank."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(rank, str(rank))


def _leaderboard_row(agent: AgentData, rank: int) -> Node:
    """Render a single leaderboard row."""
    if agent.disqualified:
        row_class = "opacity-50"
    elif agent.is_winner:
        row_class = "winner-row"
    else:
        row_class = ""

    rank_display = "⛔" if agent.disqualified else _medal(rank)

    return tr(class_=row_class)[
        # Rank medal or disqualified icon
        td(".text-center.text-xl")[rank_display],
        # Eval name
        td[
            div(".font-medium.text-text-light")[
                span(class_="line-through" if agent.disqualified else "")[agent.name],
                (
                    span(".ml-2.text-xs.text-red-400")["below threshold"]
                    if agent.disqualified
                    else None
                ),
            ],
        ],
        # Tests passed/total
        td(".text-center.tabular-nums")[
            span(".text-green-400")[str(agent.passed)],
            "/",
            span(".text-text-muted")[str(agent.total)],
        ],
        # Pass rate
        td(".text-center")[
            span(class_=f"{_pass_rate_class(agent.pass_rate)} font-semibold tabular-nums")[
                f"{agent.pass_rate:.0f}%"
            ],
        ],
        # Tokens
        td(".text-right.tabular-nums.text-text-muted")[f"{agent.tokens:,}"],
        # Cost
        td(".text-right.tabular-nums.text-text-muted")[
            format_cost(agent.cost, agent.premium_requests)
        ],
        # Duration
        td(".text-right.tabular-nums.text-text-muted")[f"{agent.duration_s:.1f}s"],
    ]


def _multi_agent_table(agents: list[AgentData]) -> Node:
    """Render the full leaderboard table."""
    return div(".card.overflow-hidden")[
        table(".leaderboard-table")[
            thead[
                tr[
                    th(".w-10")[""],
                    th["Eval"],
                    th(".text-center")["Tests"],
                    th(".text-center")["Pass Rate"],
                    th(".text-right")["Tokens"],
                    th(".text-right")["Cost"],
                    th(".text-right")["Duration"],
                ],
            ],
            tbody[*[_leaderboard_row(agent, i + 1) for i, agent in enumerate(agents)]],
        ],
    ]


def _single_agent_card(agent: AgentData) -> Node:
    """Render a single agent summary card."""
    status_class = "text-green-400" if agent.pass_rate == 100 else "text-red-400"

    return div(".card.p-5")[
        div(".flex.items-center.justify-between")[
            div(".text-lg.font-medium.text-text-light")[agent.name],
            div(".text-right")[
                div(class_=f"{status_class} text-2xl font-semibold tabular-nums")[
                    f"{agent.passed}/{agent.total}"
                ],
                div(".text-sm.text-text-muted")[
                    f"{format_cost(agent.cost, agent.premium_requests)} · {agent.tokens:,} tok"
                ],
            ],
        ],
    ]


def eval_leaderboard(agents: list[AgentData]) -> Node | None:
    """Render the eval leaderboard.

    For multiple eval configurations: Shows ranked table with medals.
    For single eval configuration: Shows summary card.
    For no configurations: Returns None.

    Args:
        agents: List of eval configurations sorted by pass_rate desc, cost asc.

    Returns:
        htpy Node or None if no configurations.
    """
    if not agents:
        return None

    if len(agents) == 1:
        return _single_agent_card(agents[0])

    return _multi_agent_table(agents)


# Keep backward-compatible alias
agent_leaderboard = eval_leaderboard
