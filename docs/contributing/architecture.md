---
description: "CopilotClient sessions, event mapping, ordinary pytest checks, and native evidence collection."
---

# Architecture

pytest-skill-engineering is built around the real GitHub Copilot runtime.

## End-to-end flow

```text
CopilotEval
  -> CopilotClient
  -> session creation
  -> streaming SDK events
  -> EventMapper
  -> CopilotResult
  -> consumer-owned pytest checks
  -> pytest plugin collection
  -> SuiteReport
  -> JSON evidence
  -> coding-agent-led investigation alongside source
```

## Main components

### 1. Copilot execution

`src/pytest_skill_engineering/copilot/`

- `eval.py` — `CopilotEval` configuration
- `runner.py` — session lifecycle, retries, and event streaming
- `events.py` — contains EventMapper, which converts SDK events into normalized result data
- `result.py` — `CopilotResult`

`max_retries` defaults to `2` for transient runtime failures.

### 2. pytest integration

`src/pytest_skill_engineering/plugin.py`

The plugin captures results and ordinary pytest outcomes, preserves genuine
pytest parameter IDs, and writes native JSON evidence.

### 3. Evidence persistence

`src/pytest_skill_engineering/reporting/`

- `collector.py` builds `SuiteReport`
- `generator.py` atomically saves JSON and loads current-schema evidence

No HTML/Markdown UI, rankings, or interpretation layer exists.
The framework owns execution and evidence;
consumers own application fixtures and verification. The companion skill guides
the existing coding agent, not a framework-owned adviser.

### 4. Serialization boundary

`src/pytest_skill_engineering/core/serialization.py`

Serialization is strict. The current report loader expects the current schema exactly and does not silently accept legacy field aliases.

## Development guidance

- preserve native evidence contracts without inventing missing data
- use deterministic round-trip and failure-path checks for persistence changes
- use real Copilot integration tests for runtime changes
