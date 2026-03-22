# Squad Decisions

## Active Decisions

### Copilot Pivot: PydanticAI Removed — Copilot SDK is the ONLY Harness (2026-03-21T18:33Z)
**Author:** Stefan (User) | **Status:** Implemented

PydanticAI eval infrastructure fully removed per user directive. Copilot SDK is now the **only** eval harness.

**What was removed (commit 622a508):**
- Files: `core/eval.py`, `execution/engine.py`, `execution/pydantic_adapter.py`, `execution/cli_toolset.py`, `execution/optimizer.py`, `fixtures/run.py`
- Dependencies: pydantic-ai, pydantic-evals, litellm, azure-identity
- Tests: 12 files, ~72 integration tests (`tests/integration/pydantic/`)

**Dependency changes:**
- Removed: `pydantic-ai>=1.61.0`, `pydantic-evals>=1.61.0`, `litellm>=1.81.13`, `azure-identity>=1.25.2`
- Added to required: `github-copilot-sdk>=0.2.0` (was optional)

**Modules rewritten for Copilot SDK (Verbal):**
1. `copilot/judge.py` (NEW) — Shared judge utility via Copilot SDK
2. `fixtures/llm_assert.py` — Uses copilot_judge()
3. `fixtures/llm_score.py` — Prompt engineering for structured output
4. `execution/clarification.py` — Uses copilot_judge()
5. `reporting/insights.py` — Copilot SDK for AI analysis

**Limitations accepted:**
- Image assertions not supported (SDK limitation) — NotImplementedError with clear message
- Token/cost tracking set to 0 in insights (would require SDK event parsing)
- Structured output via prompt engineering (not native Pydantic models)

**Commits:**
- `622a508` — refactor: remove PydanticAI engine, adapter, and eval types
- `b2098ef` — test: remove pydantic tests, update conftest for Copilot-only
- `09ff5e1` — fix: resolve leftover PydanticAI import errors
- `ce68c7c` — test: remove PydanticAI-dependent tests and fixtures

**Blocking issue:** `copilot/model.py` still has PydanticAI imports (discovered post-commit). Needs rewrite or deletion. Blocks test collection.

**Next steps:**
1. Fix `copilot/model.py` import issue (IMMEDIATE)
2. Verify test collection works
3. Run integration tests
4. Complete McManus docs rewrite for Copilot-only direction

---

### Copilot SDK Feature Parity — Sessions, Clarification, CLI, Scoring, A/B, Iterations (2026-03-21T10:50Z)
**Author:** Verbal + Hockney | **Status:** Implemented

Closed 5 of 6 remaining Copilot/Pydantic feature coverage gaps via parallel test authoring. Copilot harness now covers 11/12 feature areas.

**Key Decisions:**
1. **Sessions (test_06):** Context-in-prompt pattern (not true multi-turn) — only option with string-only SDK interface
2. **Clarification (test_07):** Response-level detection via substring matching + assertion (no engine changes)
3. **CLI (test_09):** Native Copilot shell tools (not CLIServer wrapper); tests superset of Pydantic
4. **Scoring (test_08):** LLM judge identical across harnesses; no CopilotEval changes
5. **A/B Comparison (test_10):** Instructions, not servers (Copilot doesn't use MCP); maintains report structure
6. **Iterations (test_11):** Framework-level `--aitest-iterations` flag applies to all evals

**Test Count:** 6 new files, 25 new tests (54 total collected)

**Remaining Gap:** test_12 (custom agents) — unported; requires Copilot SDK subagent dispatch investigation

**Strategic Context:** User directive (2026-03-21T10:35) confirmed: Copilot SDK is primary harness. All new features prioritized for Copilot first.

---

### Strategic Direction: Copilot SDK Primary Harness (2026-03-21T10:35Z)
**Author:** Stefan (Product Owner, via Copilot) | **Status:** Active

User directive: The project should prioritize the Copilot SDK harness over the Pydantic/Azure harness. New features should be developed in Copilot tests first. The 6 missing feature areas should be ported to Copilot tests. Documentation should reflect this priority.

**Implication:** Copilot is the primary integration testing harness. Pydantic remains as optional secondary harness for Azure/OpenAI-direct testing.

---

### Full Dependency Upgrade (2026-03-21)
**Author:** Fenster | **Status:** Verified

~40 packages upgraded via `uv lock --upgrade`. Key bumps: pydantic-ai 1.61→1.70, github-copilot-sdk 0.1→0.2, openai 2.21→2.29, ruff 0.15.1→0.15.7.

**Code changes required:** Yes (3 compatibility fixes by Hockney)
- Azure cross-tenant auth: `AZURE_TENANT_ID` env var support
- Copilot SDK 0.2.0: subagent event field rename (`eval_name`→`agent_name`)
- PydanticAI 1.70: deprecation fix (`tool()`→`tool_plain()`)
- Subagent detection fallback from tool calls

**Test results:** 105/105 integration tests passed after fixes. All static analysis passing.

**Notable transitive bumps:** mistralai 1.x→2.x, huggingface-hub 0.x→1.x, websockets 15→16 (all transitive, no direct impact).

### Copilot SDK 0.2.0 Migration (2026-03-21)
**Author:** Verbal | **Status:** Implemented & Verified

Breaking API changes addressed in 4 core copilot module files:
- `SubprocessConfig` replaces `CopilotClientOptions`
- `create_session(**kwargs)` signature (was dict)
- `send_and_wait(prompt: str)` (was dict)
- `ToolResult` fields: camelCase → snake_case
- Imports moved to `copilot` top-level

**Test verification:** 33 copilot integration tests all passed. No test code changes needed.

### Azure Tenant Configuration (2026-03-21)
**Author:** Hockney (proposed) | **Status:** Implemented

`AZURE_TENANT_ID=16b3c013-d300-468d-ac64-7eda0820b6d3` required for integration tests. Resource is in MCAPS tenant; custom token provider passes `tenant_id` to `DefaultAzureCredential.get_token()`.

**Action items:**
1. Add `AZURE_TENANT_ID` to `.env.example` — **Fenster**
2. Document in README/CONTRIBUTING — **Verbal**
3. Consider adding to CI env vars if/when CI is set up — **Fenster**

## Full Repo Review (Session 1) — 2026-03-21

Five-agent parallel repo review completed with consolidated findings across architecture, code quality, testing, reporting security, and SDK compatibility.

### Architecture Review Findings — Keaton

**Status:** Proposed

Comprehensive architecture review of pytest-skill-engineering. The project is well-structured overall — clean separation of concerns, no circular dependencies, well-typed API surface. Six findings ranked by priority.

#### 🔴 Critical

**1. `plugin.py` is a god module (1073 lines)**

Contains: CLI option registration, test lifecycle hooks, assertion recording wrappers, session message management, suite report orchestration, AI insights generation, pricing table builder, copilot model cleanup.

**Recommendation:** Extract into focused modules:
- `plugin_options.py` — `pytest_addoption`, option parsing
- `plugin_report.py` — `pytest_sessionfinish` report orchestration, `_generate_structured_insights`
- `plugin_recording.py` — `_RecordingLLMAssert`, `_RecordingLLMAssertImage`, `_RecordingLLMScore`
- Keep `plugin.py` as the thin entry point that wires hooks

This is the single highest-impact refactor available.

#### 🟡 Important

**2. `reporting/` imports from `execution/` — breaks layering**

`reporting/insights.py` imports `execution.cost.estimate_cost` and `execution.pydantic_adapter.build_model_from_string`. The `generator.py` also imports `execution.cost.models_without_pricing`.

**Recommendation:** Move `execution/cost.py` to `core/cost.py` — it's a pure pricing lookup (no execution logic). For `build_model_from_string`, pass the built model into insights rather than importing the adapter.

**3. `core/eval.py` vs `core/evals.py` — confusing naming**

`eval.py` defines `Eval`, `Provider`, `MCPServer` dataclasses. `evals.py` defines file loaders (`load_custom_agent`, `load_instruction_file`, etc.). Both are ~500 lines. The plural-s distinction is too subtle.

**Recommendation:** Rename `evals.py` → `loaders.py`. The function names already say what they do; the module name should too.

**4. `azure-identity` is a hard dependency**

Users who only use OpenAI, Anthropic, or Copilot providers are forced to install the Azure SDK. This is a ~50MB transitive footprint.

**Recommendation:** Move to an `azure` optional extra: `azure = ["azure-identity>=1.25.2"]`. Lazy-import in `core/auth.py` and `execution/pydantic_adapter.py` with a clear error message.

#### 🟢 Nice-to-have

**5. `core/serialization.py` is only consumed by `reporting/` and `cli.py`**

It doesn't serve the core domain. It's a reporting utility living in the wrong package.

**Recommendation:** Move to `reporting/serialization.py`.

**6. CONTRIBUTING.md references stale tech**

Line 126: `templates/       # Jinja2 + Tailwind HTML report templates` — the project uses htpy (Python HTML) and hand-written CSS. No Jinja2 or Tailwind anywhere.

**Recommendation:** Fix to: `templates/       # CSS + JS assets (HTML via htpy components)`

#### Things That Are Good

- **Dependency layering** is otherwise clean: core ← execution ← reporting ← fixtures ← plugin
- **`__init__.py` API surface** is well-curated with proper `__all__`
- **Optional copilot SDK** via try/except import is the right pattern
- **Type contracts** via `components/types.py` dataclasses — excellent practice
- **Pre-commit hooks** include ruff, pyright, and mkdocs build — comprehensive
- **pricing.toml** with upward directory walk is a good UX pattern
- **Test infrastructure** (integration conftest with shared constants, server fixtures) is well-organized

#### Decision Required

Items 1-4 are actionable refactors. Items 5-6 are low-risk cleanups. None require immediate action — the codebase works. But item 1 (plugin decomposition) will become increasingly painful as features are added.

**Proposed priority:** Fix #6 (5 min) → Fix #3 (30 min rename) → Fix #2 (1h move cost.py) → Fix #1 (2-3h decompose plugin) → Fix #4 (1h optional dep) → Fix #5 (15 min move)

---

### Code Review: Core + Execution Modules — Fenster

**Status:** Proposed

Reviewed: core/, execution/, fixtures/, plugin.py

#### 🔴 Critical Fixes

**serialize_dataclass deep-copy of _messages**

`core/serialization.py:20` — `dataclasses.asdict()` deep-copies every field including `EvalResult._messages` (PydanticAI `ModelMessage` objects) before the `_`-prefix filter discards them. `copy.deepcopy` on Pydantic models is fragile and expensive.

**Proposed fix:** Build the dict manually instead of using `asdict()`, skipping `_`-prefixed fields before copying, not after.

**Rate limiter session leak**

`execution/rate_limiter.py` — `reset_rate_limiters()` exists but is never called in the plugin lifecycle. Rate limiter state persists across pytest sessions in long-lived processes.

**Proposed fix:** Call `reset_rate_limiters()` in `pytest_sessionfinish` in `plugin.py`.

#### Convention Enforcement

**slots=True on all dataclasses**

Multiple dataclasses missing `slots=True`:
- `execution/pydantic_adapter.py:357` (`_ToolResult`)
- `execution/optimizer.py:38` (`InstructionSuggestion`)
- `reporting/collector.py:13,91` (`TestReport`, `SuiteReport`)
- `testing/` module classes

**Proposed rule:** Add `ruff` or custom lint to enforce `slots=True` on all `@dataclass` in `src/`.

**frozen=True for immutable config**

`Provider` and `Prompt` should use `frozen=True` per project convention. Both are config objects never mutated after construction.

#### Decision Needed

Should we fix these in a batch PR or address incrementally? The serialization bug is the highest priority — it could cause silent failures with large message histories.

---

### Report Pipeline Security Review — McManus

**Status:** Proposed

Three XSS vectors found during full reporting pipeline review. These are relevant because report content ultimately originates from LLM responses and tool execution output — both of which could be influenced by prompt injection.

#### 🔴 Critical Fixes Needed

1. **Mermaid `securityLevel: 'loose'`** → Change to `'strict'` in `scripts.js:7`
   - Loose mode allows click event bindings in Mermaid diagrams
   - Diagram code comes from LLM conversation turns — could be crafted via tool output

2. **`innerHTML` in `showDiagramHover()`** → Use `textContent` like `showDiagram()` does
   - `scripts.js:82` uses `content.innerHTML = mermaidCode` — direct HTML injection
   - The sibling function `showDiagram()` already does this correctly with `textContent`

3. **`_render_markdown()` lacks HTML sanitization** → Add sanitization before `Markup()`
   - `report.py:187` wraps `markdown.markdown()` output in `Markup()` without stripping dangerous tags
   - The `markdown` library's `extra` extension does NOT sanitize — it passes HTML through
   - LLM insights could contain `<script>`, event handlers, etc.

#### 🟡 Missing CSS Classes

Three CSS utility classes used in `test_comparison.py` are not defined in `report.css`:
- `py-1.5` (mermaid button padding)
- `py-0.5` (status badge padding)
- `hover:bg-primary/5` (mermaid button hover)

These cause broken styling on the sequence diagram button and comparison status badges.

#### 🟡 Backward-Compat Alias Violates Project Rules

`agent_leaderboard = eval_leaderboard` in `components/__init__.py` — unused externally, should be removed per "NO LEGACY CODE" rule.

**Action items:**
1. Fix 3 XSS vectors — **McManus** (immediate)
2. Add missing CSS classes — **McManus** (immediate)
3. Remove backward-compat alias — **McManus** (immediate)

---

### Test Suite Review & Findings — Hockney

**Status:** Proposed

Full audit of test coverage, harness design, fixture patterns, and gaps across all test directories.

#### 🔴 Critical

**No negative integration tests**

Every pydantic integration test asserts `result.success`. We never deliberately trigger a failure to verify the failure path works. If `result.success` is broken or always returns True, we'd never know.

**Proposal:** Add at least one test per harness (banking, todo) that expects `result.success == False` — e.g., an impossible prompt with max_turns=1.

**Copilot feature parity gap**

Copilot tests cover 6/12 of pydantic's feature areas. Missing entirely:
- Sessions (multi-turn)
- Clarification detection
- LLM scoring
- CLI servers
- A/B server comparison
- Iterations

**Question for team:** Is this intentional (CopilotEval doesn't support these features) or a gap?

#### 🟡 Important

**Sync tests in integration directory**

`test_05_skills.py` has 6 sync tests (skill loading) and `test_12_custom_agents.py` has 6 sync tests (agent file loading). These don't call any LLM — they're unit tests by nature. They run in <1 second.

**Proposal:** Either move to `tests/unit/` or accept them as "integration-adjacent" validation. Currently they inflate the integration test count without proving LLM behavior.

**Harness return type inconsistency**

Both MCP servers return JSON on success but plain string on error:
```python
if result.success:
    return json.dumps(result.value)  # JSON
return f"Error: {result.error}"      # Plain string
```

This mixed-type response could confuse LLMs. A consistent JSON envelope (`{"error": "..."}`) would be cleaner.

**Proposal:** Standardize on JSON for all MCP tool returns. This is a harness change, not a framework change.

**Todo schema parameter naming**

Schema declares `"list"` as the parameter name, but service code uses `list_name`. The MCP wrapper manually maps `args.get("list")` → `list_name`. This works but is a latent bug source.

**Proposal:** Align schema and code on the same parameter name.

#### Recommended Priority

1. Add negative/failure tests (Hockney)
2. Clarify copilot feature parity expectations (team)
3. Fix harness return type consistency (Fenster)
4. Fix todo parameter naming (Fenster)
5. Move sync tests or document the convention (Hockney)

---

### Post-0.2.0 SDK Review — Verbal

**Status:** Fix applied (bug fixed), Informational (rest)

#### 🔴 CRITICAL BUG FIXED

**`ToolInvocation.get()` broken in SDK 0.2.0**

`ToolInvocation` is no longer a TypedDict; it's a regular class. Two call sites used `.get("arguments")` which raises `AttributeError`. Fixed by replacing with `.arguments` attribute access in `copilot/model.py` and `copilot/personas.py`.

#### Team Action Items

1. **Hockney**: The history note "ToolInvocation is a TypedDict — .get('arguments') pattern still works" was incorrect. Integration tests should exercise the CopilotModel tool handler path (use `--aitest-summary-model=copilot/gpt-5-mini` with a test that has PydanticAI tools) and the subagent polyfill dispatch path.

2. **All**: When the SDK upgrades, always verify `ToolInvocation` access patterns — the SDK's own code at `copilot/tools.py:131` uses `invocation.arguments` as the reference pattern.

#### No Action Needed (Informational)

- EventMapper handles 17 of 70 event types — unhandled types are silently ignored (safe). No urgency to add handlers for new types unless we need the data.
- CopilotModel creates one session per PydanticAI request — expensive but architecturally correct for stateless model calls.
- `create_session` now accepts `on_event` kwarg — could eliminate a theoretical event race vs `session.on()`, but not a bug in practice.

---

## Implementation Log — 2026-03-21 (Sprint: Fix All Findings)

### McManus — Report Pipeline XSS & CSS Fixes
**Status:** COMPLETE  
**Changes:** Fixed 3 XSS vectors (Mermaid securityLevel, showDiagramHover innerHTML, markdown sanitization). Added missing CSS utilities (py-0.5, py-1.5, hover:bg-primary/5). Removed legacy alias. Removed duplicate inline CSS.  
**Dependency added:** nh3>=0.3.3  
**Verification:** ruff 0/errors, pyright 0/errors, HTML report regeneration successful.

### Hockney — Negative Test Cases for Pydantic Integration
**Status:** COMPLETE  
**Changes:** Added 4 negative tests to `test_01_basic.py::TestBankingNegative`: `test_tool_not_called_assertions`, `test_out_of_scope_request`, `test_max_turns_exhausted`, `test_nonexistent_account_graceful`.  
**Coverage:** Framework fundamentals (tool_was_called, semantic assertions, failure paths).  
**Note:** Tests collect cleanly (73 total) but execution deferred pending team review on max_turns=1 robustness.

### Fenster — Core Engine Fixes
**Status:** COMPLETE  
**Changes:**  
1. `serialize_dataclass`: Eliminated deep-copy of `_messages`. Uses fields() + getattr() to skip `_`-prefixed before traversal.  
2. `reset_rate_limiters()`: Now called in pytest_sessionfinish. No session leaks.  
3. Azure model cache: @lru_cache → manual dict keyed on (model_str, endpoint, tenant_id, api_key). Respects env var changes.  
4. Dataclass conventions: `slots=True` on 9 classes, `frozen=True` on Provider/Prompt, `_copilot_test` promoted to field.  
5. `plugin.py` decomposed: 1073 → 590 lines. Three submodules: plugin_recording.py, plugin_options.py, plugin_report.py.  
6. Minor fixes: YAML warnings in _extract_frontmatter, asyncio.new_event_loop() (non-deprecated).  
**Verification:** pyright 0/errors, ruff 0/errors, full test collection successful.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction

---

## Plugin System Decisions — Copilot Pivot Era (2026-03-21)

### Plugin Ecosystem Analysis & Roadmap (2026-03-21)
**Author:** Keaton (Lead) | **Status:** Strategic Proposal

Comprehensive analysis of GitHub Copilot CLI and Claude Code plugin ecosystems identified the gap areas and recommended a phased roadmap.

**Gap Analysis:**

🔴 **Critical Gaps:**
1. **Plugin Manifest Loading** (`plugin.json`) — No loader for plugin manifest. Developers must manually decompose plugins for testing.
2. **Hook Testing** — Zero support for event-driven hooks (e.g., `tool.execution_complete`, `session.start`).
3. **Multi-Plugin Composition** — Cannot test how multiple plugins interact.
4. **Plugin Config Variants** — No parameterization support for plugin settings.

🟡 **Important Gaps:**
5. **Extension Testing** (Node.js JSON-RPC) — Not supported, requires new protocol support.
6. **Claude Code Native Runner** — Currently use Copilot SDK polyfill; native runner would test real Claude Code runtime.
7. **Plugin Regression Testing** — No snapshot-based regression framework.

**Current Strengths (Already Working):**
- ✅ MCP server testing is first-class
- ✅ Custom agent loading via `.agent.md` files
- ✅ Persona system (VSCodePersona, ClaudeCodePersona, CopilotCLIPersona)
- ✅ Instruction file support (copilot-instructions.md, CLAUDE.md, etc.)
- ✅ Skill loading and composition

**Recommended Roadmap:**

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| Q1 | `load_plugin()` manifest loader | 1–2 days | Unblocks Q2, M1, M2 |
| Q2 | `Eval.from_plugin()` / `CopilotEval.from_plugin()` | 1–2 days | Primary user-facing entry point |
| Q3 | Plugin assertion helpers | 1 day | Polish |
| M1 | Hook testing framework | 1–2 weeks | Fills biggest gap |
| M2 | Multi-plugin composition | 1–2 weeks | Unique differentiator |
| M3 | Plugin config variants | 1 week | Natural parametrize extension |
| L1 | Extension testing harness (Node.js) | 2–4 weeks | Fills Node.js gap |
| L2 | Plugin regression testing | 2–3 weeks | Developer workflow |
| L3 | Claude Code native runner | 3–4 weeks | True cross-ecosystem parity |

**Key Insights:**
- Copilot CLI and Claude Code use nearly identical plugin primitives (agents, skills, MCP servers, hooks)
- pytest-skill-engineering is the only tool testing plugins holistically (not just MCP protocol or code correctness)
- Plugin-first entry points would differentiate us from existing tools (MCPBench, MCPEval, Testomat.io, MCP Inspector)

**Decision Points for Team:**
1. Should `load_plugin()` parse both Copilot CLI and Claude Code `plugin.json` formats, or start with one? **Recommendation:** Both.
2. Should hook testing be synchronous or integrated into agent runs? **Recommendation:** Start synchronous.
3. Priority of L3 (Claude Code native runner)? **Current status:** Polyfill works well, native runner only if needed.

**Status:** Strategic proposal. Ready for team decision on Phase 1 (Q1/Q2/Q3) prioritization.

---

### Plugin Support for CopilotEval (2026-03-21)
**Author:** Verbal | **Status:** Implemented

CopilotEval enhancements for unified plugin loading.

**Decisions:**
1. **`from_claude_config()`** mirrors `from_copilot_config()` — same factory pattern, different file conventions
2. **`from_plugin()`** delegates to `core.plugin.load_plugin()` — single source of truth
3. **`active_agent` and `hooks` are first-class fields** — not `extra_config` entries, for IDE autocomplete
4. **`load_mcp_config()` lives in `copilot/config.py`** — Copilot-SDK-adjacent utility
5. **Persona auto-detection in `from_plugin()`** — `.claude` directory → ClaudeCodePersona, else VSCodePersona

**Files Changed:**
- `src/pytest_skill_engineering/copilot/eval.py` — 2 new fields, 2 new classmethods
- `src/pytest_skill_engineering/copilot/config.py` — new module with `load_mcp_config()`
- `src/pytest_skill_engineering/copilot/__init__.py` — export `load_mcp_config`

**Status:** ✅ Ready (pending `core.plugin` implementation by Fenster)

---

### Plugin Test API Surface (2026-03-21)
**Author:** Hockney | **Status:** Proposed

Integration test fixtures and test files that define the expected API surface for plugin loading.

**Decisions:**
1. **`load_plugin()` returns Plugin object** with `.metadata`, `.agents`, `.skills`, `.instructions` properties
2. **`PluginMetadata` dataclass** with `name`, `version`, `description`, `author`
3. **`load_plugin()` handles both `plugin.json` and Claude Code (CLAUDE.md) layouts**
4. **`Eval.from_plugin()` creates Eval using plugin components as defaults** with explicit overrides
5. **`CopilotEval.from_claude_config()` is NEW** — distinct from `from_copilot_config()`
6. **`CopilotEval.active_agent` field** — for direct agent activation

**Test Expectations:**
- Fixture directories: `banking-plugin/` (plugin.json-based), `claude-project/` (Claude Code layout)
- Both demonstrate agent loading, skill discovery, MCP server config parsing
- Tests verify `.metadata`, `.agents`, `.skills`, `.instructions` properties

**Status:** Test API defined, implementation pending from Fenster/Verbal

---

### Plugin Ecosystem: Formats & Coverage (2026-03-21)
**Author:** Verbal | **Status:** Analysis (informational)

Detailed breakdown of plugin ecosystem structure and current test coverage.

**GitHub Copilot CLI Plugins — 7 layers:**
| Layer | Format | Our Support |
|-------|--------|------------|
| Custom Instructions | `copilot-instructions.md` | ✅ `load_instruction_file()` |
| Custom Agents | `*.agent.md` | ✅ `load_custom_agent()` |
| Skills | `SKILL.md` + `references/` | ✅ `Skill.from_path()` |
| Prompt Files | `*.prompt.md` | ✅ `load_prompt_file()` |
| MCP Servers | config dict | ✅ SDK passthrough |
| Extensions | `extension.mjs` (Node.js) | ❌ Not supported |
| Agent Plugins | `plugin.json` manifest | ❌ Not supported |

**Claude Code Plugins — Similar structure:**
| Layer | Format | Our Support |
|-------|--------|------------|
| CLAUDE.md | Markdown | ✅ `load_instruction_file()` |
| Custom Agents | `*.md` in `.claude/agents/` | ⚠️ Works but no `.claude/` auto-discovery |
| Slash Commands | `*.md` in `.claude/commands/` | ✅ `load_prompt_file()` |
| Skills | `SKILL.md` in `.claude/skills/` | ✅ `Skill.from_path()` |
| Hooks | `hooks.json` | ❌ Not supported |
| MCP Servers | `.mcp.json` | ❌ Not parsed |
| Plugins | `plugin.json` manifest | ❌ Not supported |

**Key Observations:**
- Both ecosystems converge on nearly identical primitives
- Main differences are naming conventions, dispatch mechanisms, file locations
- Persona system already handles tool-name and system-message differences correctly
- Gap is **plugin manifest loading**, not individual component support

**Status:** Informational analysis. Supports plugin ecosystem roadmap decisions.

---

### Plugin Core Design (2026-03-21)
**Author:** Fenster | **Status:** Implemented

Created `core/plugin.py` as the central plugin loading module.

**Key Choices:**

1. **Three directory layouts supported:**
   - Standalone plugin — `plugin.json` at root
   - `.github/` project config — auto-detected or explicit
   - `.claude/` project config — auto-detected or explicit
   - Rationale: Users shouldn't need `plugin.json` for standard layouts

2. **Frozen dataclasses for all config types** — `Plugin`, `PluginMetadata`, `HookDefinition` use `@dataclass(slots=True, frozen=True)`

3. **Graceful degradation on component discovery** — Single broken agent file doesn't prevent testing the rest of plugin

4. **`Eval.from_plugin()` follows existing classmethod pattern** — Mirrors `from_agent_file()`, same parameter style

5. **MCP server config is raw dicts, converted in `from_plugin()`** — Validation happens at eval construction time

**Files Changed:**
- `core/plugin.py` (NEW) — Plugin, PluginMetadata, HookDefinition, load_plugin()
- `core/eval.py` — Eval.from_plugin()
- `core/result.py` — EvalResult.tool_was_called_from_server()
- `core/__init__.py` + `__init__.py` — exports

**Open Questions for Team:**
- Should `load_plugin()` validate that referenced MCP server commands exist on disk?
- Should hooks be executable during test runs, or metadata-only for now?

**Status:** ✅ Implementation complete, awaiting team decision on hook execution model
