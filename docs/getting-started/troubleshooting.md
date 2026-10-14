# Troubleshooting

When a task cannot start, run `uv run pytest-skill-engineering doctor`. It checks
installation, project configuration, authentication, SDK startup, and access to
the starter model. When a task starts but fails an assertion, inspect its actual
output before changing configuration.

## Authentication or model access

```bash
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

## Missing or unexpected tools

Check `mcp_servers`, each server's `tools` list, and `allowed_tools` or
`excluded_tools`. Match the actual captured tool name, including any MCP server
prefix. In `client_mode="empty"`, no tools are available by default; provide them
explicitly. Skill discovery does not mean the skill was read.

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
errors, fixture state, and the source. Give your current coding agent the failure
and [saved evidence](../how-to/inspect-evidence.md) for investigation.

`final_response` can be `None`, and missing usage remains unknown rather than
zero. A timeout or tool-budget stop is a failed execution. Check `stop_reason`
and `error`; do not retry invisibly or treat incomplete evidence as success.

## Initialization conflicts

`init` refuses an existing starter or conflicting report settings. Reconcile
the named conflict explicitly, then retry. It does not overwrite your project.
