---
description: "Configure pytest-skill-engineering via pyproject.toml or command-line flags. Set up models, reports, pass rate thresholds, and provider settings."
---

# Configuration

## Quick Setup (pyproject.toml)

**Simplest — GitHub Copilot (no API keys needed):**

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.5
--llm-model=gpt-5.4-mini
--aitest-html=aitest-reports/report.html
"""
```

Requires `uv add pytest-skill-engineering` and `gh auth login`.

**Enterprise — Azure OpenAI:**

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-4.1
--aitest-html=aitest-reports/report.html
"""
```

With this configuration, just run:

```bash
pytest tests/
```

Reports are generated automatically with AI insights.

## LLM Provider Setup

pytest-skill-engineering uses the GitHub Copilot SDK for LLM access. Configure via `gh auth login` or `GITHUB_TOKEN`.

### GitHub Copilot (Required)

```bash
export AZURE_API_BASE=https://your-resource.openai.azure.com/
az login
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-xxx
```

### Other Providers

See [Pydantic AI model docs](https://ai.pydantic.dev/models/) for Anthropic, Google, etc.

### GitHub Copilot (via SDK)

You can use Copilot-accessible models for **all** LLM calls — no separate API key needed:

```bash
gh auth login  # One-time authentication
```

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.4-mini
--llm-model=copilot/gpt-5.4-mini
"""
```

Available models depend on your Copilot subscription (e.g., `gpt-5.5`, `gpt-5.4-mini`, `claude-sonnet-4.5`).

For Copilot integration tests that use auxiliary judge calls (for example optimizer integration), the suite now fails fast if no provider model is reachable. You can force the judge model with:

```bash
AITEST_INTEGRATION_JUDGE_MODEL=copilot/gpt-5.4-mini
```

| Provider | Variable |
|----------|----------|
| Azure OpenAI | `AZURE_API_BASE` + `az login` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google | `GEMINI_API_KEY` |
| GitHub Copilot | `gh auth login` or `GITHUB_TOKEN` |

## Provider Configuration

```python
from pytest_skill_engineering.copilot import CopilotEval

# Basic - Copilot SDK handles auth
agent = CopilotEval(name="assistant", model="gpt-5.4-mini")

# With generation parameters
agent = CopilotEval(
    name="assistant",
    model="gpt-4o-mini",
    temperature=0.7,
    max_tokens=1000,
)
```

## CopilotEval Configuration

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="my-agent",                         # Identifier for reports
    instructions="You are...",               # Agent instructions
    model="gpt-5.4-mini",                      # Model selection (optional)
    skill_directories=["skills/my-skill"],   # Skill directories (optional)
    custom_agents=[agent_def],               # Custom agent definitions (optional)
    excluded_tools=["tool3"],                # Filter out tools (optional)
    reasoning_effort="medium",               # Reasoning effort (optional)
)
```

## MCP Server Configuration

```python
from pytest_skill_engineering import MCPServer, Wait

server = MCPServer(
    command=["python", "-m", "my_server"],
    args=["--debug"],
    env={"API_KEY": "xxx"},
    cwd="/path/to/server",
    wait=Wait.for_tools(["tool1", "tool2"]),
)
```

See [Test MCP Servers](../how-to/test-mcp-servers.md) for complete options.

## CLI Server Configuration

```python
from pytest_skill_engineering import CLIServer

cli = CLIServer(
    name="git-cli",
    command="git",
    tool_prefix="git",
    shell="bash",
    cwd="/path/to/repo",
)
```

See [Test CLI Tools](../how-to/test-cli-tools.md) for complete options.

## Fixtures

### copilot_eval

The main fixture for running tests:

```python
async def test_banking(copilot_eval):
    agent = CopilotEval(
        name="banking",
        model="gpt-5.4-mini",
    )

    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
```

## Assertion Models

Configure the LLM judge models for semantic and visual assertions:

```toml
[tool.pytest.ini_options]
addopts = """
--llm-model=copilot/gpt-5.4-mini
--llm-vision-model=copilot/gpt-5.4-mini
"""
```

| Option | Default | Description |
|--------|---------|-------------|
| `--llm-model` | `copilot/gpt-5.4-mini` | Model for `llm_assert` semantic assertions |
| `--llm-vision-model` | Falls back to `--llm-model` | Vision model for `llm_assert_image` assertions |
| `--aitest-analysis-prompt` | Built-in prompt | Path to a custom analysis prompt file |
| `--aitest-summary-compact` | Disabled | Omit full conversation turns for passed tests in AI analysis |

## CLI Override

You can override pyproject.toml settings via CLI:

```bash
# Use a different model for this run
pytest tests/ --aitest-summary-model=copilot/gpt-5.5

# Different output path
pytest tests/ --aitest-html=custom-report.html

# Run each test 5 times for baseline stability testing
pytest tests/ --aitest-iterations=5

# Custom assertion model
pytest tests/ --llm-model=copilot/gpt-5.4-mini

# Compact AI analysis input for large suites
pytest tests/ --aitest-summary-model=copilot/gpt-5.5 --aitest-summary-compact
```

## Programmatic Prompt Access

You can retrieve the effective AI analysis prompt (CLI override → hook override → built-in default) in code:

```python
from pytest_skill_engineering import get_analysis_prompt

prompt_text = get_analysis_prompt(pytest_config)
```

To also inspect where it came from:

```python
from pytest_skill_engineering import get_analysis_prompt_details

prompt_text, source, path = get_analysis_prompt_details(pytest_config)
# source: "cli-file" | "hook" | "built-in"
# path: file path when source == "cli-file", otherwise None
```

This is useful for debugging, logging, or tooling that needs to inspect the exact prompt used for AI summary generation.
