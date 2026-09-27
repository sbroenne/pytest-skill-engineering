---
description: "Diagnose authentication, model access, MCP startup, and report generation failures."
---

# Troubleshooting

Start with:

```bash
uv run pytest-skill-engineering doctor
```

The command validates the local project, GitHub authentication, Copilot SDK
startup, and access to `gpt-5.6-sol`. It exits nonzero when any check fails.

## GitHub authentication fails

For local development, authenticate the GitHub CLI:

```bash
gh auth login --hostname github.com
gh auth status --hostname github.com
```

For CI, set `GITHUB_TOKEN` or `GH_TOKEN`. `GITHUB_TOKEN` takes precedence when
both exist. The selected account must have GitHub Copilot access.

## The model is unavailable

The starter requires `gpt-5.6-sol`. `doctor` prints the model IDs available to
the authenticated account when that model is absent. Model access is controlled
by GitHub Copilot and organization policy; pytest-skill-engineering does not
silently substitute a different model.

## An MCP server does not start

Run the exact command from the eval's `mcp_servers` entry in the same virtual
environment. For a Python module:

```bash
uv run python -m your_package.your_mcp_module
```

Check that the command exists, imports succeed, and the process writes protocol
messages—not logs—to standard output.

## Report generation requires a model

HTML and Markdown reports require AI analysis. Configure it explicitly:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.6-sol
--aitest-html=aitest-reports/report.html
--aitest-json=aitest-reports/results.json
"""
```

If analysis fails after test execution, the JSON evidence is still written.
Regenerate the report after fixing authentication or model access:

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json \
  --html aitest-reports/report.html \
  --summary \
  --summary-model copilot/gpt-5.6-sol
```

## Initialization reports a conflict

`pytest-skill-engineering init` does not overwrite
`tests/test_copilot_eval.py` or replace existing values for its report flags.
The error names the conflicting file or option. Reconcile it explicitly, then
run `init` again.
