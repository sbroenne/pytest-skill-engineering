# pytest-copilot - pytest for GitHub Copilot

**Test whether GitHub Copilot can complete tasks with your tools and instructions.**

Independently maintained; not an official GitHub product or endorsed by GitHub.

pytest-copilot runs real GitHub Copilot sessions from pytest and saves their
execution as JSON. Use it for MCP servers, CLI tools, skills, system prompts,
plugins, and custom agents.

Each test has three parts:

1. Configure a session with `CopilotTask`.
2. Send a user task through the `copilot_run` fixture.
3. Check the actual output with ordinary assertions.

The framework manages sessions, limits, usage, and captured evidence. You supply
the application fixtures and success criteria. A completed session or a tool call
does not establish that the task succeeded; check files, application state, or
operation output.

## Start here

[Getting started](getting-started/index.md) walks through installation, the
bundled Todo MCP test, and the saved result. You need Python 3.11+, uv, and GitHub
Copilot access. Live tests may consume premium requests.

## Find the right guide

| Goal | Start here |
| --- | --- |
| Run a first test | [Getting started](getting-started/index.md) |
| Test your own interface | [Task guides](how-to/index.md) |
| Compare two configurations | [Comparisons](getting-started/comparing.md) |
| Investigate a failure | [Inspect evidence](how-to/inspect-evidence.md) |
| Look up a setting or result field | [Reference](reference/index.md) |
| Understand execution and verification | [Explanation](explanation/index.md) |
| Upgrade from an earlier version | [Upgrading to 2.0](migration.md) |

## Learn from recorded experiments

The [companion-skill study](use-cases/companion-skill.md) and
[Excel skill study](use-cases/excel-skill-value.md) show how fixed output checks
can test whether added guidance helps. They are historical observations, not
setup requirements or promises about future runs.
