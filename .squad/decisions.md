# Squad Decisions

## Active Decisions

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

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
