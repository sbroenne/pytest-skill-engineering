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

## First useful result

```bash
uv add pytest-skill-engineering
gh auth login --hostname github.com
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
uv run python -m pytest tests/test_copilot_eval.py -v
```

This creates and runs one real `gpt-5.6-sol` eval against a bundled Todo MCP
server. Open `aitest-reports/report.html` to inspect the tool call and AI
analysis. The run may consume Copilot premium requests.

## Core ideas

- **Copilot-only execution** — the public harness is `CopilotEval`
- **Current default** — the generated starter uses `gpt-5.6-sol`
- **Opt-in expensive comparisons** — add larger models only when the comparison is worth the cost
- **Report-first debugging** — failures should tell you what to fix next

## Choose your path

| Goal | Start here |
|---|---|
| Prove the installation works | [Getting Started](getting-started/index.md) |
| Test an MCP server | [Test MCP Servers](how-to/test-mcp-servers.md) |
| Test a CLI | [Test CLI Tools](how-to/test-cli-tools.md) |
| Test an Agent Skill | [Test Coding Agents](how-to/test-coding-agents.md#testing-skills) |
| Test a custom agent | [Custom Agents](getting-started/custom-agents.md) |
| Test a complete plugin | [Test Plugins](how-to/test-plugins.md) |
| Understand or regenerate reports | [Generate Reports](how-to/generate-reports.md) |
| Diagnose a failed first run | [Troubleshooting](getting-started/troubleshooting.md) |
