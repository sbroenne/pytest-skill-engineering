# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

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
