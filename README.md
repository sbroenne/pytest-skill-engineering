# pytest-skill-engineering

[![PyPI version](https://img.shields.io/pypi/v/pytest-skill-engineering)](https://pypi.org/project/pytest-skill-engineering/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-skill-engineering)](https://pypi.org/project/pytest-skill-engineering/)
[![CI](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Skill Engineering. Test-driven. AI-analyzed.**

A pytest plugin for skill engineering — test your MCP server tools, prompt templates, agent skills, and custom agents with real LLMs. Red/Green/Refactor for the skill stack. Let AI analysis tell you what to fix.

## Why?

Modern AI systems are built on **skill engineering** — the discipline of designing modular, reliable, callable capabilities that an LLM can discover, invoke, and orchestrate to perform real tasks. Skills are what separate "text generator" from "agent that actually does things."

An MCP server is the runtime for those skills. It doesn't ship alone — it comes bundled with the **full skill engineering stack**: **tools** (callable functions), **prompt templates** (server-side reasoning starters), **agent skills** (domain knowledge and behavioral guidelines), and **custom agents** (specialist sub-agents). Users layer on their own **prompt files** (slash commands like `/review`) on top.

Your unit tests cover the server code. Nothing covers the skill stack. And the skill stack is what the LLM actually sees.

**Skill engineering breaks in ways code tests can't catch:**

- The tool description is too vague — the LLM picks the wrong tool or passes garbage parameters
- The prompt template renders correctly but the assembled message confuses the LLM
- A prompt file's slash command produces garbage output because the instructions are ambiguous
- The skill has the right facts but is structured so poorly the LLM skips it
- The custom agent has the right tools listed but the description is too vague to trigger dispatch

**And when you're improving it — how do you know version A is better than version B?**

Skill engineering is iterative — prompt tuning, tool description refinement, custom agent instructions, skill structure. You need A/B testing built in. Run both versions, same prompts, and let the leaderboard tell you which one wins on pass rate and cost.

That's what pytest-skill-engineering does: test the full skill engineering stack, compare variants, and get AI analysis that tells you exactly what to fix.

## How It Works

Write tests as natural language prompts — you assert on what the agent did. If a test fails, your tool descriptions or skill need work, not your code:

1. **Write a test** — a prompt that describes what a user would say
2. **Run it** — the LLM tries to use your tools and fails
3. **Fix the interface** — improve tool descriptions, schemas, or prompts until it passes
4. **AI analysis tells you what else to optimize** — cost, redundant calls, unused tools

pytest-skill-engineering has two harnesses — pick the one that fits your setup:

### Eval + `eval_run` — bring your own model

Bundle any LLM with your MCP server and assert on what happened:

```python
from pytest_skill_engineering import Eval, Provider, MCPServer

async def test_balance_query(eval_run):
    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[MCPServer(command=["python", "-m", "my_banking_server"])],
    )
    result = await eval_run(agent, "What's my checking balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
```

Best for: full control over the test loop — pick any model, compare variants, introspect every tool call. No Copilot subscription required.

### CopilotEval + `copilot_eval` — use the real Copilot CLI

No model setup. No API keys. Copilot handles MCP OAuth automatically.

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_agent(copilot_eval):
    agent = CopilotEval(skill_directories=["skills/my-skill"])
    result = await copilot_eval(agent, "What can you help me with?")
    assert result.success
```

Best for: testing exactly what your users experience — Copilot manages all MCP connections (including OAuth), loads skills natively, and runs the same model your users have.

→ [Choosing a Test Harness](https://sbroenne.github.io/pytest-skill-engineering/explanation/choosing-a-harness/)

## AI Analysis

AI analyzes your results and tells you **what to fix**: which model to deploy, how to improve tool descriptions, where to cut costs. [See a sample report →](https://sbroenne.github.io/pytest-skill-engineering/demo/hero-report.html)

![AI Analysis — winner recommendation, metrics, and comparative analysis](screenshots/ai_analysis.png)

## Quick Start

**Using GitHub Copilot? Zero setup:**

```bash
uv add pytest-skill-engineering[copilot]
gh auth login  # one-time
pytest tests/
```

**Using your own model (Azure, OpenAI, Anthropic…):**

```bash
uv add pytest-skill-engineering
export AZURE_API_BASE=https://your-resource.openai.azure.com/
az login
pytest tests/
```

### AI Analysis judge model (optional but recommended)

The AI analysis report needs a model to generate insights. Configure it in `pyproject.toml`:

**GitHub Copilot:**

```toml
[tool.pytest.ini_options]
addopts = "--aitest-summary-model=copilot/gpt-5-mini"
```

**Azure OpenAI:**

```toml
[tool.pytest.ini_options]
addopts = "--aitest-summary-model=azure/gpt-5.2-chat"
```

## Features

- **MCP Server Testing** — Real models against real tool interfaces and bundled prompt templates
- **Prompt File Testing** — Test VS Code `.prompt.md` and Claude Code command files (slash commands) with `load_prompt_file()` / `load_prompt_files()`
- **CLI Server Testing** — Wrap CLIs as testable tool servers
- **Copilot Skill Testing** — `CopilotEval + copilot_eval` for end-to-end tests using the real Copilot CLI (native OAuth, skill loading, exact user experience)
- **Custom Eval Testing** — Load `.agent.md` files with `Eval.from_agent_file()` to test agent instructions, or A/B test agent versions; use `load_custom_agent()` + `CopilotEval` to test real subagent dispatch
- **Eval Comparison** — Compare models, skills, custom agent versions, and server configurations
- **Eval Leaderboard** — Auto-ranked by pass rate and cost
- **Multi-Turn Sessions** — Test conversations that build on context
- **AI Analysis** — Actionable feedback on tool descriptions, prompts, and costs
- **Multi-Provider** — Any model via [Pydantic AI](https://ai.pydantic.dev/) (OpenAI, Anthropic, Gemini, Azure, Bedrock, Mistral, and more)
- **Copilot SDK Provider** — Use `copilot/gpt-5-mini` for all LLM calls (judge, insights, scoring) — zero additional setup with `pytest-skill-engineering[copilot]`
- **Clarification Detection** — Catch agents that ask questions instead of acting
- **Semantic Assertions** — Built-in `llm_assert` fixture powered by [pydantic-evals](https://ai.pydantic.dev/evals/) LLM judge
- **Multi-Dimension Scoring** — `llm_score` fixture for granular quality measurement across named dimensions
- **Image Assertions** — `llm_assert_image` for AI-graded visual evaluation of screenshots and charts
- **Cost Estimation** — Automatic per-test cost tracking with pricing from litellm + custom overrides

## Who This Is For

- **MCP server authors** — Validate that LLMs can actually use your tools
- **Copilot skill and agent authors** — Test exactly what your users experience, before you ship
- **Eval builders** — Compare models, prompts, and skills to find the best configuration
- **Teams shipping AI systems** — Catch LLM-facing regressions in CI/CD

## Documentation

📚 **[Full Documentation](https://sbroenne.github.io/pytest-skill-engineering/)**

## Requirements

- Python 3.11+
- pytest 9.0+
- An LLM provider (Azure, OpenAI, Anthropic, etc.) **or** a GitHub Copilot subscription (`pytest-skill-engineering[copilot]`)

## Acknowledgments

Inspired by [agent-benchmark](https://github.com/mykhaliev/agent-benchmark).

## License

MIT
