# Squad Decisions

## Active Decisions

### Full Dependency Upgrade (2026-03-21)
**Author:** Fenster | **Status:** Informational

~40 packages upgraded via `uv lock --upgrade`. Key bumps: pydantic-ai 1.61→1.70, github-copilot-sdk 0.1→0.2, openai 2.21→2.29, ruff 0.15.1→0.15.7. No code changes required. All static analysis passed. Risk: low.

**Notable transitive bumps:** mistralai 1.x→2.x, huggingface-hub 0.x→1.x, websockets 15→16 (all transitive, no direct impact).

### Copilot SDK 0.2.0 Migration (2026-07-23)
**Author:** Verbal | **Status:** Implemented

Breaking API changes addressed in 4 core copilot module files:
- `SubprocessConfig` replaces `CopilotClientOptions`
- `create_session(**kwargs)` signature (was dict)
- `send_and_wait(prompt: str)` (was dict)
- `ToolResult` fields: camelCase → snake_case
- Imports moved to `copilot` top-level

All linting and type checking passed. No test changes needed.

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
