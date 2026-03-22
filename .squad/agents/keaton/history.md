# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, **Copilot SDK only** (PydanticAI removed 2026-03-21), MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21
- **Current Phase:** Copilot-only pivot complete. Plugin system design phase.

## Cross-Agent Context

### 2026-03-21 — Copilot Pivot Session (COMPLETE)

**Directive:** User decision (2026-03-21T10:35Z) to remove PydanticAI harness and make Copilot SDK the **only** eval infrastructure.

**What Keaton did in this session:**
- Completed plugin testing ecosystem analysis covering GitHub Copilot CLI and Claude Code
- Identified 4 critical gaps (plugin manifest loading, hook testing, multi-plugin composition, extension testing) and recommended 9-item roadmap
- Proposed Copilot CLI & Claude Code unified plugin loading (single `load_plugin()` parser for both)
- Strategic insight: pytest-skill-engineering is unique in testing plugins holistically (others test only single layers: MCP protocol, code correctness, model capability)
- Recommendation: Prioritize Q1/Q2/Q3 quick wins (plugin loaders + assertions) before M1-M3 (hook testing, composition)

**Cross-team parallel work:**
- **Fenster:** Removed 6 core PydanticAI files, deleted dependencies
- **Verbal:** Rewrote 6 modules to use Copilot SDK
- **Hockney:** Deleted `tests/integration/pydantic/` (12 test files), discovered `copilot/model.py` blocker
- **McManus:** Docs rewrite (IN PROGRESS)

**Impact on plugin system:** The plugin ecosystem analysis informs plugin loading design. Fenster/Verbal will implement `core/plugin.py` + `Eval.from_plugin()` + `CopilotEval.from_plugin()` based on this analysis.

---

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### Plugin Testing Architecture Analysis (2026-03-21)

Completed strategic analysis of plugin testing gaps for Copilot CLI and Claude Code ecosystems. Key findings:

**Current coverage is strong for individual components** — MCP servers, custom agents (both synthetic and real dispatch), skills, instruction files, prompt files, CLIs, and personas all have test support. The persona system (`VSCodePersona`, `ClaudeCodePersona`, `CopilotCLIPersona`) is the right abstraction for cross-ecosystem testing.

**Critical gaps are at the composition layer:**
1. No `plugin.json` manifest loader — users must manually decompose plugins into components
2. No hook testing — hooks are a core plugin primitive with zero test support
3. No multi-plugin composition testing — individual plugins pass, combined environment breaks
4. No extension testing (Node.js JSON-RPC) — most powerful Copilot CLI mechanism is untestable

**Both ecosystems converge on identical primitives:** agents, skills, MCP servers, hooks, instructions. The `plugin.json` manifest format is similar. A single `load_plugin()` parser could handle both.

**Competitive landscape is single-layer:** MCPBench, MCPEval, LiveMCPBench test MCP protocol compliance only. No tool tests plugins holistically as a composition of MCP + agents + skills + hooks + instructions. This is our unique differentiation.

**Recommended priority:** Quick wins first — `load_plugin()` and `from_plugin()` factory methods (1-2 days each, glue code over existing infrastructure). Then hook testing and multi-plugin composition (1-2 weeks each). Native Claude Code runner is Phase 3 — the persona polyfill works well.

Filed decision document: `.squad/decisions/inbox/keaton-plugin-testing-analysis.md`

### Architecture Review (2026-03-21)

**Project size:** ~13,900 LOC across src/, 10 subpackages, 50+ modules.

**Module hierarchy (clean):** `core/` → `execution/` → `reporting/` → `fixtures/` → `plugin.py`. No circular deps. One intentional cross-layer import: `reporting/insights.py` imports `execution/cost.py` for pricing lookups.

**Key files by size:**
- `plugin.py` (1073 lines) — god module, largest file, handles options, session lifecycle, report orchestration, assertion recording, AI insights wiring, pricing table generation
- `reporting/generator.py` (637), `reporting/insights.py` (611) — appropriately sized
- `core/eval.py` (510) + `core/evals.py` (474) — confusingly named pair; `eval.py` = dataclasses, `evals.py` = file loaders

**Dependency observations:**
- `litellm` used only for `model_cost` pricing dict (2 files). Heavy transitive dep for a lookup table.
- `mdutils` used only in `reporting/markdown.py` (465 lines). Lightweight, appropriate.
- `azure-identity` hard dep — forces Azure SDK install even for non-Azure users.
- `pydantic-evals` used only in `fixtures/llm_assert.py` for `judge_output`.

**Config quality:** ruff, pyright, pytest, pre-commit all well-configured. pyright excludes `copilot/` (likely due to optional SDK). Line-length 100. Markers comprehensive.

**Documentation:** CONTRIBUTING.md says "Jinja2 + Tailwind" but project uses htpy + hand-written CSS — stale.

**API surface:** `__init__.py` exports 48 names (core) + 8 (copilot). Clean try/except pattern for optional copilot SDK. `__all__` maintained.

**Improvement areas:**
1. `plugin.py` needs decomposition (report orchestration, pricing, option parsing could extract)
2. `reporting` → `execution` import breaks layering (cost module could live in `core/`)
3. `eval.py` / `evals.py` naming is confusing (suggest `eval.py` + `loaders.py`)
4. `azure-identity` as hard dep excludes non-Azure users
5. `core/serialization.py` only consumed by `reporting/` and `cli.py` — misplaced
6. CONTRIBUTING.md has stale technology references

### Full Repo Review (2026-03-21)

Completed comprehensive architecture review as part of 5-agent session. Filed 6 findings (1 critical, 3 important, 2 nice-to-have) in formal decision document. Highest-impact item: decompose 1073-line `plugin.py` god module into focused sub-modules (`plugin_options.py`, `plugin_report.py`, `plugin_recording.py`). Positive notes: excellent dependency layering, well-curated API surface, optional SDK pattern, type contracts in `components/types.py`, comprehensive pre-commit hooks.
