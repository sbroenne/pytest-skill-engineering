# Core Engine Fixes — Fenster (2026-03-21)

**Status:** Implemented & Verified

All findings from the repo review session have been fixed.

## Changes Made

### Critical Fixes

1. **serialize_dataclass deep-copy eliminated** — `core/serialization.py` no longer calls `dataclasses.asdict()`. Uses `dataclasses.fields()` + `getattr()` to skip `_`-prefixed fields before any traversal. `_messages` with large PydanticAI objects is never deep-copied.

2. **Rate limiter reset in plugin lifecycle** — `reset_rate_limiters()` now called in `pytest_sessionfinish`. Rate limiter state no longer leaks across sessions.

3. **Azure model cache respects env var changes** — `@lru_cache` replaced with manual dict keyed on `(model_str, azure_endpoint, tenant_id, api_key)`. Changing `AZURE_API_BASE` or `AZURE_TENANT_ID` mid-process produces a new model instance.

### Convention Fixes

4. **Dataclass conventions enforced** — `slots=True` added to 9 dataclasses. `frozen=True` added to `Provider` and `Prompt`. `TestReport._copilot_test` promoted from dynamic attribute to proper field.

5. **plugin.py decomposed** — 1073 → 590 lines. Three new submodules: `plugin_recording.py`, `plugin_options.py`, `plugin_report.py`. All pytest hooks remain in `plugin.py`.

6. **Minor fixes** — `_extract_frontmatter` warns on YAML errors. `_shutdown_copilot_model_client` uses `asyncio.new_event_loop()` (not deprecated `get_event_loop()`).

## Verification

- pyright: 0 errors
- ruff: 0 errors
- Test collection: 73 pydantic + 29 copilot + 650 unit tests all collect
- Public API unchanged (imports from `plugin` still resolve)
