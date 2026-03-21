# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, **Copilot SDK only** (PydanticAI removed 2026-03-21), MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21
- **Current Phase:** Copilot-only pivot complete. Plugin system design phase.

## Cross-Agent Context

### 2026-03-21 — Copilot Pivot Session (IN PROGRESS)

**Directive:** User decision (2026-03-21T10:35Z) to remove PydanticAI harness and make Copilot SDK the **only** eval infrastructure.

**What McManus is doing in this session:**
- Docs rewrite for Copilot-only direction (IN PROGRESS)
  - README.md: Remove PydanticAI references, emphasize Copilot harness
  - CONTRIBUTING.md: Update dev workflow (only copilot integration tests)
  - docs/architecture.md: Update diagrams for Copilot-only flow
  - docs/testing.md: Consolidate to single harness
  - CHANGELOG.md: v0.3.0 release notes for PydanticAI removal
- **Blocked on:** `copilot/model.py` import fix (can't verify docs examples work without test collection)

**Cross-team parallel work:**
- **Fenster:** Removed 6 core PydanticAI files, deleted dependencies
- **Verbal:** Rewrote 6 modules to use Copilot SDK
- **Hockney:** Deleted `tests/integration/pydantic/` (12 test files, ~72 tests), discovered `copilot/model.py` blocker
- **Coordinator:** Fixed leftover import errors

**BLOCKER discovered by Hockney:** `copilot/model.py` still has PydanticAI imports. Blocks all test collection.

---

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

### Full Repo Review (2026-03-21)

Completed full reporting pipeline security review as part of 5-agent session. Filed 6 findings (3 critical XSS vectors, 3 CSS/alias issues) in formal decision document. **Critical XSS fixes:** (1) Mermaid securityLevel 'loose'→'strict', (2) showDiagramHover() innerHTML→textContent, (3) _render_markdown() add HTML sanitization. **CSS fixes:** Add missing py-1.5, py-0.5, hover:bg-primary/5 utility classes. **Code cleanup:** Remove backward-compat agent_leaderboard alias. All items immediate priority.

### XSS & CSS Fixes Applied (2026-03-21)

All 6 findings from the repo review are now fixed:

1. **Mermaid securityLevel** — `'loose'` → `'strict'` in scripts.js. Prevents click-handler injection in diagrams.
2. **showDiagramHover() innerHTML** — Changed to `textContent`. Mermaid.js still picks it up via `mermaid.run()`.
3. **_render_markdown() sanitization** — Added `nh3` (Rust-based HTML sanitizer) with explicit tag/attribute allowlist. Preserves `<pre class="mermaid">` for diagram rendering while stripping `<script>`, event handlers, etc. `nh3>=0.3.3` added to pyproject.toml.
4. **Missing CSS utilities** — Added `py-0.5`, `py-1.5`, `hover:bg-primary/5` to report.css in the correct utility sections.
5. **Legacy alias removed** — Deleted `agent_leaderboard = eval_leaderboard` from `agent_leaderboard.py` and its `__all__` entry from `__init__.py`. Not used anywhere externally.
6. **Duplicate inline CSS removed** — Removed `_grid_styles()` function from `test_grid.py` and inline `<style>` block from `overlay()`. Both rule sets already exist in `report.css` (lines 986-1000). CSS file is now the single source of truth.

**Key design decision:** Used `nh3` over `bleach` (deprecated) or regex. `nh3` is Rust-backed, zero-config secure defaults, and the allowlist approach ensures we only permit safe HTML elements that markdown legitimately produces.
