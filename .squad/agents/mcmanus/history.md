# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-21 — Full Reporting Pipeline Review

**Architecture:**
- Pipeline: TestReport → SuiteReport → build_suite_report() → AI Insights → generate_html()/generate_json()/generate_md()
- htpy components in `reporting/components/` render typed dataclasses from `types.py`
- CSS is hand-written Tailwind-equivalent utilities + semantic component classes (~1000 lines)
- JS handles Mermaid rendering, agent comparison, test filtering, overlay diagrams
- Markdown report in `reporting/markdown.py` mirrors HTML structure 1:1 using mdutils

**Component patterns:**
- Every component is a function returning `Node | None` (None = skip rendering)
- `types.py` has TypedDict-like dataclasses (actually `@dataclass(slots=True)`) as contracts
- `format_cost()` is duplicated in `agent_leaderboard.py` and `markdown.py` — needs shared util
- `_build_report_context()` in generator.py is the bridge from SuiteReport → ReportContext

**CSS structure:**
- Design tokens → Preflight reset → Base styles → Utility classes → Component classes → AI visualization classes
- All utility classes mirror Tailwind naming convention (no build step)
- Three CSS classes used in components but NOT defined: `py-1.5`, `py-0.5`, `hover:bg-primary/5`

**Security findings (flagged):**
- Mermaid `securityLevel: 'loose'` enables click handlers in diagrams — XSS vector
- `showDiagramHover()` uses `innerHTML` with mermaid code — XSS vector (vs `showDiagram()` which correctly uses `textContent`)
- `_render_markdown()` passes LLM output through `Markup()` without sanitization
- `collector.py` dataclasses don't use `slots=True` (deviates from project convention)

**Backward-compat alias:**
- `agent_leaderboard = eval_leaderboard` in `__init__.py` + `__all__` — never imported externally, violates no-legacy-code rule
