# pytest-skill-engineering

A test runner and evidence recorder for people working with coding agents.

Run real Copilot tasks against MCP servers, CLI tools, skills, system prompts,
plugins, and custom agents. Check the actual result with ordinary pytest
assertions. Let your existing coding agent investigate the evidence and source.
The framework has no separate AI judge, report adviser, or skill refiner.

## First useful result

```powershell
uv add pytest-skill-engineering
gh auth login --hostname github.com
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
uv run python -m pytest "tests\test_copilot_eval.py" -v
```

Live execution may consume premium requests. pytest shows whether your checks
passed; saved JSON records the execution. Your coding agent interprets that
evidence alongside the source. A completed session is not independently
verified task success: define concrete output checks.

## Choose your path

| Goal | Start here |
| --- | --- |
| Run a first test | [Getting started](getting-started/index.md) |
| Investigate results with your coding agent | [Inspecting evidence](how-to/inspect-evidence.md) |
| See how we tested whether a skill helps a coding agent | [Real-world case study](use-cases/companion-skill.md) |
| Test an MCP server | [MCP server testing](how-to/test-mcp-servers.md) |
| Test a CLI | [CLI testing](how-to/test-cli-tools.md) |
| Compare a skill or system prompt | [Comparisons](getting-started/comparing.md) |
| Test a custom agent definition | [Custom agents](getting-started/custom-agents.md) |
| Investigate saved execution | [Inspect evidence](how-to/inspect-evidence.md) |
| Upgrade from 0.6.x | [1.0 migration](migration.md) |
