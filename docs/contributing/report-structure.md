---
description: "HTML report component structure: agent leaderboard, test grid, comparison view, sequence diagrams, and AI insights layout."
---

# Report Structure

The visual structure and components of pytest-skill-engineering HTML reports.

## Design Philosophy

Reports answer one question: **"Which configuration should I deploy?"**

Every visual element supports this goal through:

1. **Progressive disclosure** — Summary first, details on demand
2. **Comparison-first** — Winner highlighting, sorted rankings
3. **Scalability** — Works for 2 agents or 20 agents
4. **Actionable insights** — Not just metrics, but what to fix

## Implementation

Reports are generated using [htpy](https://htpy.dev/) - a type-safe HTML generation library. Components are Python functions in `src/pytest_skill_engineering/reporting/components/`.

## Report Sections

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. HEADER                                                       │
│    Suite name, status badge, metrics                            │
├─────────────────────────────────────────────────────────────────┤
│ 2. AI ANALYSIS                                                  │
│    LLM-generated markdown (insights.markdown_summary)           │
├─────────────────────────────────────────────────────────────────┤
│ 3. AGENT LEADERBOARD (if > 1 agent)                             │
│    Ranked table of configurations                               │
├─────────────────────────────────────────────────────────────────┤
│ 4. AGENT SELECTOR (if > 2 agents)                               │
│    Pick 2 agents for side-by-side comparison                    │
├─────────────────────────────────────────────────────────────────┤
│ 5. TEST RESULTS                                                 │
│    Filter buttons + test cards with comparison columns          │
├─────────────────────────────────────────────────────────────────┤
│ 6. OVERLAY (hidden by default)                                  │
│    Fullscreen mermaid diagram viewer                            │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Header

Suite identity and key metrics at the top of the report.

**Component:** `report.py` → `_report_header()`

### Components

| Component | Content | Example |
|-----------|---------|---------|
| **Suite Title** | Module docstring or "Test Report" | "Banking API Integration Tests" |
| **Status Badge** | Pass/fail with visual styling | ✅ All Passed or ✗ 2 Failed |
| **Metrics Bar** | Key numbers | tests, duration, cost, AI analysis cost |

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Banking API Integration Tests                    ✅ All Passed  │
├─────────────────────────────────────────────────────────────────┤
│ 4 tests │ 12.3s │ $0.004 │ 🤖 $0.002                            │
└─────────────────────────────────────────────────────────────────┘
```

## 2. AI Analysis

LLM-generated markdown rendered directly. The AI writes analysis prose that's displayed as-is.

**Component:** `report.py` → `_ai_insights_section()`

The `insights.markdown_summary` field contains the complete analysis as markdown, converted to HTML via the `markdown` library.

Features:
- **Toggle button** — Collapse/expand the section
- **Markdown styling** — Headers, lists, code blocks, etc.

For details on what the AI analyzes and how insights are generated, see [AI Analysis](../explanation/ai-analysis.md).

## 3. Eval Leaderboard

**Only shown when multiple agents are tested.**

**Component:** `agent_leaderboard.py` → `agent_leaderboard()`

Answers: "Which configuration should I deploy?"

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ 🏆 Eval Leaderboard                                            │
├─────────────────────────────────────────────────────────────────┤
│ Rank │ Eval                          │ Pass │ Tokens │ Cost   │
├──────┼────────────────────────────────┼──────┼────────┼────────┤
│  🥇  │ gpt-4.1-mini / concise         │ 100% │  561 ★ │ $0.001 │
│  🥈  │ gpt-5-mini / concise           │ 100% │  743   │ $0.001 │
│  🥉  │ gpt-4.1-mini / detailed        │ 100% │  764   │ $0.001 │
│   4  │ gpt-5-mini / detailed          │ 100% │  973   │ $0.002 │
└──────┴────────────────────────────────┴──────┴────────┴────────┘
  ★ = Best in column    Sorted by: Pass Rate → Cost (tiebreaker)
```

### Features

- **Medals** (🥇🥈🥉) for top 3
- **Pass rate bar** (visual progress)
- **Star (★)** on best-in-column values
- **Winner row highlighting** (green background)
- **Full agent identity**: Model + Prompt name + Skill name

## 4. Eval Selector

**Only shown when more than 2 agents are tested.**

**Component:** `agent_selector.py` → `agent_selector()`

Allows picking exactly 2 agents for side-by-side comparison in test details.

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Compare agents:                                                 │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐        │
│ │ ☑ gpt-4.1-mini │ │ ☑ gpt-5-mini   │ │ ☐ gpt-5-mini   │        │
│ │   100% ✓       │ │   100% ✓       │ │   + skill      │        │
│ └────────────────┘ └────────────────┘ └────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### Behavior

- **Exactly 2 selected** — Always maintains 2 agents selected
- **Click to swap** — Clicking a third agent replaces the oldest selection
- **Cannot deselect below 2** — Clicking selected agent does nothing
- **Visual feedback** — Selected chips have highlighted border

## 5. Test Results

All test results with comparison columns for selected agents.

**Components:** 
- `test_grid.py` → `test_grid()` (main container)
- `test_comparison.py` → `test_comparison()` (per-test details)

### Filter Buttons

```
┌─────────────────────────────────────────────────────────────────┐
│ [All (4)] [Failed (0)]                                          │
└─────────────────────────────────────────────────────────────────┘
```

### Test Card (Collapsed)

```
┌─────────────────────────────────────────────────────────────────┐
│ ▶ Check account balance                   ✅ passed │ 4.6s     │
└─────────────────────────────────────────────────────────────────┘
```

### Test Card (Expanded)

Shows side-by-side comparison of selected agents:

```
┌─────────────────────────────────────────────────────────────────┐
│ ▼ Check account balance                   ✅ passed │ 4.6s     │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐ ┌─────────────────────────┐         │
│ │ gpt-4.1-mini           ✅│ │ gpt-5-mini             ✅│         │
│ │ 561 tokens │ $0.001     │ │ 743 tokens │ $0.002     │         │
│ ├─────────────────────────┤ ├─────────────────────────┤         │
│ │   [Mermaid Diagram]     │ │   [Mermaid Diagram]     │         │
│ ├─────────────────────────┤ ├─────────────────────────┤         │
│ │ Final Response:         │ │ Final Response:         │         │
│ │ Balance: $1,500.00...   │ │ Your checking balance...│         │
│ └─────────────────────────┘ └─────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### Session Grouping

Multi-turn sessions appear as grouped test cards with visual connectors:

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔗 Session: banking-flow                    3 tests │ all ✅   │
├─────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ ▼ Check account balance                   ✅ │ 2.1s       │   │
│ │ [comparison columns...]                                   │   │
│ └───────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                     Context carried                             │
│                          │                                      │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ ▼ Transfer to savings                     ✅ │ 3.4s       │   │
│ │ [comparison columns...]                                   │   │
│ └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 6. Overlay

Fullscreen mermaid diagram viewer. Hidden by default, triggered by clicking a diagram.

**Component:** `overlay.py` → `overlay()`

### Features

- **Click diagram to enlarge** — Opens in fullscreen overlay
- **Click outside to close** — Dismiss by clicking backdrop
- **Re-renders at full size** — Diagram redrawn for maximum readability

## Adaptive Behavior

The report layout adapts based on what was tested:

| Scenario | Leaderboard | Eval Selector | Comparison Columns |
|----------|-------------|----------------|-------------------|
| 1 agent | ❌ | ❌ | ❌ (single column) |
| 2 agents | ✅ | ❌ | ✅ (both shown) |
| 3+ agents | ✅ | ✅ | ✅ (pick 2) |
| Sessions | Based on agent count | Based on agent count | ✅ |

### Detection Logic

```python
if len(agents) == 1:
    # Simple mode: no comparison UI
    show_leaderboard = False
    show_selector = False
elif len(agents) == 2:
    # Two-agent mode: comparison but no selector needed
    show_leaderboard = True
    show_selector = False
else:
    # Multi-agent mode: full comparison UI
    show_leaderboard = True
    show_selector = True
```

## Scalability Requirements

The design MUST work at these scales:

| Scale | Behavior |
|-------|----------|
| 2 agents | Leaderboard with 2 rows, no selector |
| 3-6 agents | Selector chips in single row |
| 8+ agents | Selector chips wrap to multiple rows |
| 20+ agents | Leaderboard with pagination |
| 50+ tests | All tests rendered, browser scroll |

### Anti-Patterns (What NOT to Do)

❌ **Don't** show side-by-side cards that shrink with more items  
❌ **Don't** truncate agent names — wrap or tooltip instead  
❌ **Don't** show tiny unreadable diagrams  
❌ **Don't** require horizontal scrolling for core content  
❌ **Don't** select more than 2 agents for comparison

## Visual Design Tokens

Consistent styling from Material Design (indigo theme):

| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#4051b5` | Primary actions, highlights |
| Pass | `#22c55e` | Success states |
| Fail | `#ef4444` | Error states |
| Card BG | `#282c34` | Card backgrounds |
| Surface | `#1e2129` | Page background |
| Border radius | `4px` | Consistent Material feel |
| Font | `Roboto` | Body text |
| Mono font | `Roboto Mono` | Code, metrics |

## Implementation Files

Components are Python functions generating HTML via htpy:

| File | Purpose |
|------|---------|
| `components/report.py` | Main report, header, AI analysis |
| `components/agent_leaderboard.py` | Ranked agent table |
| `components/agent_selector.py` | Eval comparison picker |
| `components/test_grid.py` | Test list with filter buttons |
| `components/test_comparison.py` | Side-by-side agent results |
| `components/overlay.py` | Fullscreen diagram viewer |
| `components/types.py` | Data types for components |
| `templates/partials/tailwind.css` | All CSS styles |
| `templates/partials/scripts.js` | Client-side interactions |

## Key Principles

1. **Exactly 2 for comparison** — Always compare exactly 2 agents, no more
2. **AI explains, components display** — AI writes insights in markdown
3. **Sessions are grouping, not special** — Same test cards, visual connectors
4. **Progressive disclosure** — Click to expand details
5. **No redundancy** — Each piece of information appears once

## Testing Matrix

Visual tests use stable JSON fixtures in `tests/fixtures/reports/`:

| Fixture | Agents | Sessions | What to Test |
|---------|--------|----------|--------------|
| `01_single_agent.json` | 1 | No | Header, AI Analysis, Test grid (no comparison) |
| `02_multi_agent.json` | 2 | No | Leaderboard, Comparison columns (no selector) |
| `03_multi_agent_sessions.json` | 2 | Yes | Session grouping, Leaderboard (no selector) |
| `04_agent_selector.json` | 3 | No | Eval selector, Leaderboard with medals, Selection behavior |

### Test Checklist by Fixture

**01_single_agent.json:**

- [ ] Header shows suite name and status badge
- [ ] AI Analysis section renders markdown
- [ ] AI Analysis toggle button works
- [ ] Test cards expand/collapse
- [ ] Mermaid diagrams render
- [ ] Filter buttons work (all/failed)
- [ ] NO leaderboard shown
- [ ] NO agent selector shown
- [ ] NO comparison columns (single column only)

**02_multi_agent.json:**

- [ ] Leaderboard shows 2 agents
- [ ] Winner row highlighted
- [ ] Both comparison columns visible
- [ ] NO agent selector (only 2 agents)
- [ ] Mermaid overlay opens on click
- [ ] Overlay closes on backdrop click

**03_multi_agent_sessions.json:**

- [ ] Session grouping with visual connectors
- [ ] Session header shows test count and status
- [ ] Leaderboard shows 2 agents
- [ ] NO agent selector (only 2 agents)
- [ ] Both comparison columns visible

**04_agent_selector.json:**

- [ ] Leaderboard shows 3 agents with medals (🥇🥈🥉)
- [ ] Winner row highlighted
- [ ] Eval selector shows 3 chips
- [ ] Exactly 2 agents selected by default
- [ ] Clicking 3rd agent swaps selection
- [ ] Cannot deselect to less than 2
- [ ] Comparison columns show side-by-side
- [ ] Hidden columns update when selection changes
