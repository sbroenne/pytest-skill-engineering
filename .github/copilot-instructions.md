# Copilot instructions for pytest-skill-engineering

## Product boundary

This repository serves people working with coding agents. It provides reliable
Copilot task execution, controls, ordinary pytest output, and saved JSON evidence.

- Use `CopilotEval` and the `copilot_eval` pytest fixture.
- Consumers own application fixtures, guarded tool adapters, and independent
  output verification. The framework owns SDK sessions, request controls, usage,
  evidence, and native JSON. The coding agent interprets results.
- Never add a separate SDK runner, model retry loop, usage collector, competing
  benchmark report, AI judge, report adviser, or skill refiner.
- There is no framework companion skill. Keep framework usage in documentation,
  examples, and helpful errors. Consumer-provided skill evaluation remains
  supported; historical case-study guidance is a test fixture, not a product.
- Session completion, tool presence, and a model's claims are not independent
  task verification. Use ordinary assertions against actual output.
- A/B entries share one pytest outcome. Save side-specific verification; never
  invent independent pass rates or causal improvement from that shared outcome.

## Clean contracts

- No backward compatibility, legacy formats, fallback readers, or deprecated
  aliases. Missing required data is an explicit error.
- Current native reports use schema 4.0. Never hand-edit generated JSON. Fix
  its producer and regenerate.
- Preserve missing-versus-empty output, nullable usage, completion flags, capture
  errors, request auditing, and missing-pricing warnings.
- Preserve audited transport shutdown before SDK-client shutdown.
- Surface errors rather than returning success-shaped defaults.

## Terminology

- **System prompt**: instructions configuring behavior (`CopilotEval.instructions`).
- **Prompt**: the user task passed to `copilot_eval`.
- **Custom agent**: a `.agent.md` definition, not inherently a subagent.
- **Custom agent dispatch**: the runtime routing under test.
- **Subagent**: only an actual runtime invocation such as `result.subagent_invocations`.
- **Eval**: the test harness, not the interface under test.

## Python and tools

Use Python 3.11+, `from __future__ import annotations`, annotated public APIs,
async execution, and slotted dataclasses. Prefer immutable configuration,
existing helpers, precise types, and small changes. Follow current repository
patterns instead of adding unrelated abstraction.

Use `uv` exclusively; never use bare pip or bare pytest.

```powershell
uv sync --frozen --all-extras
uv run ruff check src tests examples
uv run ruff format --check src tests examples
uv run pyright
```

Do not bypass pre-commit hooks or force commits. Never commit credentials.
Do not revert changes belonging to someone else.

## Validation

Run the smallest checks covering the change. For execution or AI-facing behavior,
run relevant real-Copilot integration files sequentially. Fix failures before
moving on, and rerun only affected failed cases:

```powershell
uv run python -m pytest "tests\integration\copilot\test_01_basic.py" -v
```

Offline control and evidence contracts prove framework behavior, not model
performance. Use them when paid calls or desktop input are forbidden; never
pretend fake-SDK results establish AI-interface quality.

```powershell
uv run python -m pytest "tests\contracts" -q -o addopts=
```

## Evidence and documentation changes

There are no HTML/Markdown renderers, dashboards, rankings, report assets, or
demo-report generators. Do not recreate them. Keep native evidence lossless and
validate persistence failures with offline contracts, then run relevant live
cases when execution behavior changes.

Update directly related documentation, code examples, CLI help, navigation, and
release guidance. Historical changelog entries remain historical.

```powershell
uv run python -X utf8 -m mkdocs build --strict
uv build
```

The framework records outcomes and evidence without interpretation. Subjective
review belongs to the current coding agent or a human and must not be presented
as measured success.
