# Contributing

Thanks for improving pytest-copilot.

## Development setup

```bash
git clone https://github.com/sbroenne/pytest-copilot.git
cd pytest-copilot
uv sync --frozen --all-extras
uv run --frozen pre-commit install
uv run --frozen pytest-copilot --version
uv run --frozen python -m pytest tests/contracts/ -q -o addopts=
```

The final command is a deterministic setup check and does not call Copilot.

Authenticate Copilot with either:

```bash
gh auth login --hostname github.com
```

or an explicit token in your environment. Eval sessions use
`GITHUB_TOKEN` first, then `GH_TOKEN`; when neither is set, the SDK uses its
signed-in user.

## What this project validates

This project validates the **AI interface** around tools:

- tool descriptions and schemas
- system prompts
- skills
- custom agents
- prompt files

The main harness is `CopilotTask`. Keep new contributions on the current Copilot-only public API surface.

For ordinary CLI tests, use `create_command_tool` with a caller-selected
executable and a separate argument array. This also applies to help, setup,
discovery, and supporting commands for every CLI. Keep native product commands
and help; do not require a shell or MCP wrapper. Consumers still own application
guards and independent checks. Keep tests of actual shell features, such as
pipelines and redirection, explicitly separate.

## Validation workflow

Use the smallest command that proves the change you made.

| Change | Required validation |
|---|---|
| Python source | Ruff, Ruff format, Pyright, relevant contract checks, then relevant Copilot integration file |
| Copilot execution or system prompt | Relevant `tests/integration/copilot/` file with a real model |
| Docs only | `uv run --frozen python -X utf8 -m mkdocs build --strict` |
| Evidence collection or serialization | Offline round-trip/failure-path contracts and relevant real-Copilot coverage |
| Dependencies | Refresh `uv.lock`, then run the checks for the affected source |

### Locked dependency environment

CI, integration, and documentation workflows use `uv sync --frozen`
and `uv run --frozen` to consume the committed lock without resolving against a
runner's different default registry. `--frozen` does not check whether the lock
is current with `pyproject.toml`; dependency changes must regenerate and validate
the lock explicitly. Use `--frozen` on local validation commands when consuming
the existing lock in an environment with a different default registry.

Resolve dependency updates through public PyPI (`https://pypi.org/simple/`).
Both committed locks use PyPI and record artifact URLs and hashes from
`files.pythonhosted.org`. A package proxy can lag PyPI and may not contain
versions this project already requires.

Refresh both locks when updating dependencies, then install from the main lock:

```bash
uv lock --upgrade --default-index https://pypi.org/simple/
uv lock --upgrade --project examples/skill-dogfood --default-index https://pypi.org/simple/
uv lock --check --default-index https://pypi.org/simple/
uv lock --check --project examples/skill-dogfood --default-index https://pypi.org/simple/
uv sync --frozen --all-extras
```

Keep dependency requirements consistent with the updated locks. Do not rewrite
lock URLs by hand or disable certificate verification.

### Deterministic checks

Run the checks that cover the changed surface:

```bash
uv run --frozen ruff check src tests
uv run --frozen ruff format --check src tests
uv run --frozen ruff check examples/skill-dogfood
uv run --frozen ruff format --check examples/skill-dogfood
uv run --frozen pyright
uv run --frozen python -X utf8 -m mkdocs build --strict
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

When paid requests or desktop activity are explicitly forbidden, run the relevant
offline checks instead and state that real-model behavior was not verified.
Do not run live cases merely to complete the checklist.

Run integration files one at a time. Fix every failure before moving to the
next file, and use `--lf` rather than repeating successful, paid runs.

### Customer workflow and historical case study

[`examples/skill-dogfood`](examples/skill-dogfood/) preserves the historical
write-run-fix-rerun experiment with frozen guidance fixtures, not a distributed
companion skill. Default collection is offline; comparisons are explicit live
cases. It has no dedicated workflow. `test_19_customer_workflow.py` reuses the
ordinary no-skill workflow as regression coverage.

The sample's fixed checks remain outside model-writable files. Preserve real
before/after evidence and unchanged authored tests. A failed control case stays
visible; one pair does not prove a skill advantage. Keep the sample's separate
lock current when its manifest or the local framework dependency changes.

## Evidence collection

The framework supplies ordinary pytest output and structured JSON evidence.
It does not render dashboards, rank configurations, or interpret outcomes.
Preserve captured configuration, arguments, outputs, errors, completion flags,
nullable usage, request audits, and consumer-recorded verification properties.
Never hand-edit generated JSON; fix its producer and run the relevant check.

## Architecture

See `docs/contributing/architecture.md` for the current Copilot pipeline:

`CopilotClient -> session -> EventMapper -> CopilotResult -> ordinary pytest checks -> collected JSON evidence`

## Terminology

Use these terms consistently:

- **system prompt** — `CopilotTask.instructions`
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
