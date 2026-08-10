# Contributing

Thanks for improving pytest-skill-engineering.

## Development setup

```bash
uv sync
uv run pre-commit install
```

Authenticate Copilot with either:

```bash
gh auth login
```

or `GITHUB_TOKEN` in your environment.

## What this project validates

This project validates the **AI interface** around tools:

- tool descriptions and schemas
- system prompts
- skills
- custom agents
- prompt files

The main harness is `CopilotEval`. Keep new contributions on the current Copilot-only public API surface.

## Validation workflow

Use the smallest command that proves the change you made.

### Source-only changes

For report generation, serialization, and documentation source changes, run focused deterministic checks:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run mkdocs build --strict
uv run python scripts/generate_fixture_html.py
```

These checks validate source correctness, but they do **not** prove agent behavior.

### Agent-behavior changes

For anything that changes Copilot execution, run real Copilot integration tests:

```bash
uv run python -m pytest tests/integration/copilot/test_01_basic.py -v
uv run python -m pytest --lf tests/integration/copilot/ -v
```

Slow or model-comparison coverage is opt-in:

```bash
uv run python -m pytest tests/integration/copilot/test_02_models.py -v --run-slow
```

Do not claim success from mock-only tests.

## Report development

When you change report components, contracts, CSS, or JS, regenerate from existing JSON instead of re-running LLM tests:

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json   --html aitest-reports/report.html
```

## Architecture

See `docs/contributing/architecture.md` for the current Copilot pipeline:

`CopilotClient -> session -> EventMapper -> CopilotResult -> pytest plugin -> suite report -> HTML/Markdown/JSON`

## Terminology

Use these terms consistently:

- **system prompt** — `CopilotEval.instructions`
- **prompt** — the user task you send into the eval
- **custom agent** — a `.agent.md` definition
- **custom agent dispatch** — when Copilot routes work to a custom agent
- **subagent** — only the runtime invocation/result event
