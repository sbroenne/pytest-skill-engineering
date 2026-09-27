# Contributing

Thanks for improving pytest-skill-engineering.

## Development setup

```bash
git clone https://github.com/sbroenne/pytest-skill-engineering.git
cd pytest-skill-engineering
uv sync --frozen --all-extras
uv run --frozen pre-commit install
uv run --frozen pytest-skill-engineering --version
uv run --frozen python -m pytest tests/contracts/ -q -o addopts=
```

The final command is a deterministic setup check and does not call Copilot.

Authenticate Copilot with either:

```bash
gh auth login --hostname github.com
```

or an explicit token in your environment. Eval and judge sessions use
`GITHUB_TOKEN` first, then `GH_TOKEN`; when neither is set, the SDK uses its
signed-in user.

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

| Change | Required validation |
|---|---|
| Python source | Ruff, Ruff format, Pyright, relevant contract checks, then relevant Copilot integration file |
| Copilot execution or system prompt | Relevant `tests/integration/copilot/` file with a real model |
| Docs only | `uv run --frozen python -X utf8 -m mkdocs build --strict` |
| Report Python, CSS, or JavaScript | Regenerate every fixture report, inspect the rendered HTML, and run relevant deterministic checks |
| Dependencies | Refresh `uv.lock`, then run the checks for the affected source |

### Locked dependency environment

CI, integration, hero-test, and documentation workflows use `uv sync --frozen`
and `uv run --frozen` to consume the committed lock without resolving against a
runner's different default registry. `--frozen` does not check whether the lock
is current with `pyproject.toml`; dependency changes must regenerate and validate
the lock explicitly. Use `--frozen` on local validation commands when consuming
the existing lock in an environment with a different default registry.

This development environment intentionally uses
`https://packagefeedproxy.microsoft.io/pypi/simple/`. Resolve updates through the
configured proxy rather than overriding it with the public PyPI index. The
committed lock records proxy artifact URLs and hashes; installations from it
have succeeded locally and on GitHub-hosted CI runners. Direct access to
`files.pythonhosted.org` is not required for this verified installation path.

Package availability on the proxy may lag public PyPI. An update therefore uses
the newest compatible releases available through the configured source, not
necessarily the newest public releases. Refresh the lock through the proxy when
newer versions become available. Do not rewrite lock URLs by hand or disable
certificate verification.

### Deterministic checks

Run the checks that cover the changed surface:

```bash
uv run --frozen ruff check src tests
uv run --frozen ruff format --check src tests
uv run --frozen pyright
uv run --frozen python -X utf8 -m mkdocs build --strict
uv run --frozen python scripts/generate_fixture_html.py
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

Run integration files one at a time. Fix every failure before moving to the
next file, and use `--lf` rather than repeating successful, paid runs.

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

## Good first contributions

Documentation corrections, a focused diagnostics check, and a single missing
contract assertion are good starting points. Comment on an issue before taking
larger work so the intended behavior and validation scope are explicit.

Every pull request should explain the user-visible outcome and list the exact
commands run. Do not include credentials, raw tokens, or unsanitized private
prompts in issues or reports.
