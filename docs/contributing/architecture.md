---
description: "Current contributor architecture: CopilotClient sessions, event mapping, result collection, pytest hooks, and report generation."
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
  -> pytest plugin collection
  -> SuiteReport
  -> JSON / Markdown / HTML report generation
  -> optional AI insights
```

## Main components

### 1. Copilot execution

`src/pytest_skill_engineering/copilot/`

- `eval.py` — `CopilotEval` configuration
- `runner.py` — session lifecycle, retries, and event streaming
- `events.py` — contains EventMapper, which converts SDK events into normalized result data
- `result.py` — `CopilotResult`
- `judge.py` — semantic judging helpers such as `llm_assert`

`max_retries` defaults to `2` for transient runtime failures.

### 2. pytest integration

`src/pytest_skill_engineering/plugin.py`

The plugin captures completed results, attaches stable eval identity, preserves genuine pytest parameter IDs, and writes normalized JSON for report generation.

### 3. Reporting pipeline

`src/pytest_skill_engineering/reporting/`

- `collector.py` builds `SuiteReport`
- `generator.py` renders HTML, Markdown, and JSON
- `insights.py` generates cached AI analysis
- `components/` contains the htpy UI

Reports key comparisons by stable agent identity and display human-readable labels separately.

### 4. Serialization boundary

`src/pytest_skill_engineering/core/serialization.py`

Serialization is strict. The current report loader expects the current schema exactly and does not silently accept legacy field aliases.

## Development guidance

- change typed report contracts before changing components
- regenerate reports from saved JSON for template work
- use deterministic checks for report source changes
- use real Copilot integration tests for runtime changes
