---
description: "CopilotClient sessions, event mapping, ordinary pytest checks, and native evidence collection."
---

# Architecture

The framework creates real Copilot SDK sessions and records what happened.
Application fixtures and independent output checks belong to the consumer.

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
```

After the run, a coding agent or human can inspect the JSON alongside source.
That investigation is not another framework execution stage.

## Main components

### Copilot execution

`src/pytest_skill_engineering/copilot/`

- `eval.py` — `CopilotEval` configuration
- `runner.py` — single-attempt session lifecycle and event streaming
- `events.py` — `EventMapper`, which converts SDK events into result records
- `result.py` — `CopilotResult`
- `requests.py` — actual outgoing request auditing
- `skills.py` — explicit skill validation and pre-send SDK discovery

Each call makes one attempt and preserves its failure evidence. The framework
does not start replacement sessions after startup or execution failures.

Audited transports must shut down before their owning SDK client. Cleanup
events and errors are captured before the final result is built.

### pytest integration

`src/pytest_skill_engineering/plugin.py`

The plugin captures results and ordinary pytest outcomes, preserves genuine
pytest parameter IDs, and writes native JSON evidence.

Consumer assertions determine the pytest verdict. A captured session's
`success` flag is not an independent task verdict.

### Evidence persistence

`src/pytest_skill_engineering/reporting/`

- `collector.py` builds `SuiteReport`
- `generator.py` atomically saves JSON and loads current-schema evidence

The persistence layer records execution and outcomes without interpreting them.
It does not render a dashboard, rank configurations, or select a winner.

### Serialization boundary

`src/pytest_skill_engineering/core/serialization.py`

Serialization is strict. The loader requires schema 4.0 and all required
fields; it does not fill missing records from defaults or accept legacy aliases.
See [evidence structure](evidence-structure.md) for the lossless-data contract.

## Development guidance

Use deterministic round-trip and failure-path contracts for persistence
changes. Use relevant real-Copilot integration files for execution changes.
Never treat fake SDK behavior as proof of model performance.
