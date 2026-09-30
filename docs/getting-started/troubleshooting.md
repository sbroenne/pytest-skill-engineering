# Troubleshooting

Start with `uv run pytest-skill-engineering doctor` for installation,
project configuration, authentication, SDK startup, and starter-model access.

## Authentication or model access

```powershell
gh auth login --hostname github.com
gh auth status --hostname github.com
```

The runtime selects `GITHUB_TOKEN` before `GH_TOKEN`, then the SDK's signed-in
user. The selected account needs Copilot access. The starter requires
`gpt-5.6-sol`; unavailable models are reported, not silently substituted.

## MCP startup

Run the configured server command in the same environment. Check imports,
permissions, and protocol output. Logs belong on stderr, not protocol stdout.
Do not "fix" a startup failure by weakening the output criterion.

## Retired arguments or old reports

Version 1.0 removed HTML/Markdown, summary, analysis, and judge flags. Remove them from
configuration and CI using the [migration guide](../migration.md).
Old JSON schemas are rejected; rerun their producer with 1.x. Never hand-edit
JSON or invent missing fields.

## Saving evidence fails

Check the destination path, directory permissions, and the printed error.
Verification properties must contain JSON-compatible values. Failed publication
keeps a previous file intact but makes the current command return nonzero.
An old output file is not evidence that this run succeeded.

## Session succeeds but the test fails

Session success is not task correctness. Inspect actual outputs and
`record_property` checks. Check call completion, operation errors, capture
errors, fixture state, and the source. Ask your current coding agent to use the
[companion skill](companion-skill.md) for an evidence-backed investigation.

## Initialization conflicts

`init` refuses an existing starter or conflicting report settings. Reconcile
the named conflict explicitly, then retry. It does not overwrite your project.
