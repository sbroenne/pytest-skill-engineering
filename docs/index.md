---
description: "Test MCP servers, CLI workflows, skills, prompt files, and custom agents with the real GitHub Copilot coding agent."
---

# pytest-skill-engineering

pytest-skill-engineering helps you test whether **GitHub Copilot can actually use what you built**.

It focuses on the AI-facing surface area:

- tool descriptions and schemas
- system prompts
- skills
- custom agents
- prompt files
- report quality and remediation guidance

## Quick start

```bash
uv add pytest-skill-engineering
gh auth login
```

Write a `CopilotEval`, attach your MCP servers with `mcp_servers={...}`, run `uv run python -m pytest`, then inspect the report.

## Core ideas

- **Copilot-only execution** — the public harness is `CopilotEval`
- **Economical default** — start with `gpt-5.4-mini`
- **Opt-in expensive comparisons** — add larger models only when the comparison is worth the cost
- **Report-first debugging** — failures should tell you what to fix next

## Start here

- [Getting Started](getting-started/index.md)
- [How to Test MCP Servers](how-to/test-mcp-servers.md)
- [How to Generate Reports](how-to/generate-reports.md)
- [Reference](reference/index.md)
