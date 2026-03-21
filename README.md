# pytest-skill-engineering

[![PyPI version](https://img.shields.io/pypi/v/pytest-skill-engineering)](https://pypi.org/project/pytest-skill-engineering/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-skill-engineering)](https://pypi.org/project/pytest-skill-engineering/)
[![CI](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Test-Driven Skill Engineering for GitHub Copilot**

Test MCP servers, CLI tools, Agent Skills, and custom agents using the **real GitHub Copilot coding agent**. Write tests as prompts, run them against actual Copilot sessions, and get AI-powered insights on what to fix.

## Why?

Your MCP server passes all unit tests. Then a user tries it in GitHub Copilot and:

- Copilot picks the wrong tool
- Passes garbage parameters  
- Can't recover from errors
- Ignores your skill's instructions

**Why?** Because you tested the code, not the AI interface.

For LLMs, your API isn't functions and types — it's **tool descriptions, Agent Skills, custom agent instructions, and schemas**. These are what GitHub Copilot actually sees. Traditional tests can't validate them.

**The key insight: your test is a prompt.** You write what a user would say ("What's my checking balance?"), and Copilot figures out how to use your tools. If it can't, your AI interface needs work.

## What This Tests

pytest-skill-engineering validates the **full skill engineering stack** that ships with your MCP server:

- **MCP Server Tools** — Can Copilot discover and call your tools correctly?
- **Agent Skills** ([agentskills.io](https://agentskills.io) spec-compliant) — Does domain knowledge improve performance?
- **Custom Agents** (`.agent.md` files) — Do your specialist instructions trigger proper subagent dispatch?
- **MCP Prompt Templates** — Do server-side templates produce the right behavior?
- **CLI Tools** — Can Copilot use command-line interfaces effectively?

Plus **A/B testing**, **multi-turn sessions**, **clarification detection**, and **AI-powered reports** that tell you exactly what to fix.

## How It Works

Write tests as prompts. Run them with the real GitHub Copilot coding agent. Assert on what happened:

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_balance_query(copilot_eval):
    agent = CopilotEval(
        skill_directories=["skills/banking-advisor"],
        max_turns=10,
    )
    result = await copilot_eval(agent, "What's my checking balance?")
    
    assert result.success
    assert result.tool_was_called("get_balance")
```

**The workflow:**

1. **Write a test** — a prompt that describes what a user would say
2. **Run it** — GitHub Copilot tries to use your tools
3. **Fix the interface** — improve tool descriptions, skills, or agent instructions until it passes
4. **AI analysis tells you what to optimize** — cost, redundant calls, better prompts

If a test fails, your AI interface needs work, not your code.

## Agent Skills — First-Class Support

pytest-skill-engineering provides **full [Agent Skills](https://agentskills.io) spec compliance**:

- **Compatibility field** — Mark required tools, models, or platforms
- **Metadata** — Title, description, version, attribution
- **Allowed-tools** — Restrict which tools the agent can use
- **Scripts & Assets** — Package Python scripts, prompts, and resources
- **Eval Bridge** — Import evals from `evals/evals.json`, export grading results

Agent Skills are loaded natively when testing with `CopilotEval` — exactly as users experience them.

## AI-Powered Reports

AI analyzes your results and tells you **what to fix**: which configuration to deploy, how to improve tool descriptions, where to cut costs. [See a sample report →](https://sbroenne.github.io/pytest-skill-engineering/demo/hero-report.html)

![AI Analysis — winner recommendation, metrics, and comparative analysis](screenshots/ai_analysis.png)

## Quick Start

```bash
# Install
uv add pytest-skill-engineering

# Authenticate (one-time)
gh auth login

# Run tests
pytest tests/
```

### Configure AI Analysis (optional but recommended)

The AI-powered report needs a model to generate insights. Configure it in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "--aitest-summary-model=copilot/gpt-5-mini"
```

You can also use Azure OpenAI or other providers if you prefer — see [Configuration](https://sbroenne.github.io/pytest-skill-engineering/reference/configuration/).

## Features

- **MCP Server Testing** — Test tools, prompt templates, and bundled skills with real Copilot sessions
- **Agent Skills** — Full [agentskills.io](https://agentskills.io) spec compliance (compatibility, metadata, allowed-tools, evals bridge)
- **Custom Agents** — Test `.agent.md` files and validate subagent dispatch
- **CLI Tool Testing** — Verify Copilot can use command-line interfaces
- **Plugin Testing** — Load complete plugin directories (plugin.json, .github/, .claude/ layouts) with auto-discovery
- **A/B Testing** — Compare instructions, skills, custom agent versions, or tool configurations
- **Eval Leaderboard** — Auto-ranked by pass rate and cost
- **Multi-Turn Sessions** — Test conversations that build on context
- **Clarification Detection** — Catch agents that ask questions instead of acting
- **LLM Assertions** — Semantic checks with `llm_assert`, multi-dimension scoring with `llm_score`, image evaluation with `llm_assert_image`
- **AI-Powered Reports** — Actionable feedback on tool descriptions, prompts, and costs
- **Cost Tracking** — Copilot premium request tracking + USD estimation via `pricing.toml`

## Who This Is For

- **MCP server authors** — Validate that GitHub Copilot can actually use your tools
- **Agent Skills authors** — Test skills exactly as users experience them in Copilot
- **Custom agent builders** — Validate `.agent.md` instructions and subagent dispatch
- **Plugin developers** — Test complete GitHub Copilot CLI plugins end-to-end
- **Teams shipping Copilot integrations** — Catch skill stack regressions in CI/CD

## Documentation

📚 **[Full Documentation](https://sbroenne.github.io/pytest-skill-engineering/)**

## Requirements

- Python 3.11+
- pytest 9.0+
- GitHub Copilot subscription (required)

## Acknowledgments

Inspired by [agent-benchmark](https://github.com/mykhaliev/agent-benchmark).

## License

MIT
