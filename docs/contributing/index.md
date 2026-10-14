---
description: "Contribute to pytest-skill-engineering: development setup, coding standards, and project architecture."
---

# Contributing

This section is for changes to the framework itself. To write tests for your own
tools, use [getting started](../getting-started/index.md).

## Set up the checkout

```bash
git clone https://github.com/sbroenne/pytest-skill-engineering.git
cd pytest-skill-engineering
uv sync --frozen --all-extras
uv run --frozen pre-commit install
uv run --frozen pytest-skill-engineering --version
uv run --frozen python -m pytest tests/contracts/ -q -o addopts=
```

The contract checks do not call Copilot. Consume the committed lock with
`--frozen`; dependency changes must regenerate and validate it explicitly.

## Validate the changed behavior

| Change | Validation |
| --- | --- |
| Python source | Ruff, formatting, Pyright, affected contracts, and relevant Copilot integration coverage |
| Copilot execution or AI-facing behavior | Relevant real-Copilot integration files, sequentially |
| Documentation | `uv run --frozen python -X utf8 -m mkdocs build --strict` |
| Evidence persistence | Native JSON round-trip and failure-path contracts |
| Historical workflow sample | Sample offline checks; live comparisons only when explicitly authorized |

Offline tests prove framework contracts, not model performance. Fix a failed
live case before moving on; rerun only affected failures rather than repeating
successful paid execution.

The
[full contribution guide](https://github.com/sbroenne/pytest-skill-engineering/blob/main/CONTRIBUTING.md)
contains exact commands, dependency-registry guidance, and PR expectations.
All PRs are squash merged.

## Keep the product boundary clear

The framework owns Copilot sessions, controls, usage, and evidence. Consumers
own application fixtures, guarded tool adapters, and output verification.
Investigation belongs to the coding agent or a human; do not add a second
runner, AI judge, dashboard, ranking system, or companion skill.

The [workflow sample](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/skill-dogfood)
preserves a historical skill experiment as test data. Its no-skill workflow is
reused by `test_19_customer_workflow.py`; default sample checks stay offline.

## Maintainer references

| Topic | Guide |
| --- | --- |
| Session lifecycle and plugin integration | [Architecture](architecture.md) |
| Data contracts and persistence checks | [Evidence structure](evidence-structure.md) |
| Versioning and release workflow | [Releasing](releasing.md) |
