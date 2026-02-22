---
description: "Configure pytest-aitest via pyproject.toml or command-line flags. Set up models, reports, pass rate thresholds, and provider settings."
---

# Configuration

## Quick Setup (pyproject.toml)

**Simplest — GitHub Copilot (no API keys needed):**

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5-mini
--llm-model=copilot/gpt-5-mini
--aitest-html=aitest-reports/report.html
"""
```

Requires `uv add pytest-aitest[copilot]` and `gh auth login`.

**Enterprise — Azure OpenAI:**

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

With this configuration, just run:

```bash
pytest tests/
```

Reports are generated automatically with AI insights.

## LLM Provider Setup

pytest-aitest uses [Pydantic AI](https://ai.pydantic.dev/) for LLM access. Configure via environment variables.

### Azure OpenAI (Enterprise / CI)

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

If you have `pytest-aitest[copilot]` installed, you can use Copilot-accessible models for **all** LLM calls — no separate API key needed:

```bash
gh auth login  # One-time authentication
```

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5-mini
--llm-model=copilot/gpt-5-mini
"""
```

Available models depend on your Copilot subscription (e.g., `gpt-5-mini`, `gpt-5.2`, `claude-opus-4.5`).

For Copilot integration tests that use auxiliary judge calls (for example optimizer integration), the suite now fails fast if no provider model is reachable. You can force the judge model with:

```bash
AITEST_INTEGRATION_JUDGE_MODEL=copilot/gpt-5-mini
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
from pytest_aitest import Provider

# Basic - Pydantic AI handles auth via env vars
provider = Provider(model="azure/gpt-5-mini")

# With generation parameters
provider = Provider(
    model="openai/gpt-4o-mini",
    temperature=0.7,
    max_tokens=1000,
)

# With rate limits (model-specific)
provider = Provider(
    model="azure/gpt-5-mini",
    rpm=10,    # Requests per minute
    tpm=10000, # Tokens per minute
)
```

## Agent Configuration

```python
from pytest_aitest import Agent, ClarificationDetection, Provider, MCPServer

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],               # MCP servers
    cli_servers=[cli],                  # CLI servers (optional)
    system_prompt="You are...",         # System prompt (optional)
    skill=my_skill,                     # Agent Skill (optional)
    max_turns=10,                       # Max tool-call rounds
    retries=3,                          # Max retries on tool errors (default: 1)
    name="my-agent",                    # Identifier for reports (optional)
    allowed_tools=["tool1", "tool2"],   # Filter tools (optional, reduces tokens)
    clarification_detection=ClarificationDetection(enabled=True),  # Detect clarification questions
)
```

## MCP Server Configuration

```python
from pytest_aitest import MCPServer, Wait

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
from pytest_aitest import CLIServer

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

### aitest_run

The main fixture for running tests:

```python
async def test_banking(aitest_run):
    agent = Agent(
        name="banking",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.success
```

## Assertion Models

Configure the LLM judge models for semantic and visual assertions:

```toml
[tool.pytest.ini_options]
addopts = """
--llm-model=azure/gpt-5-mini
--llm-vision-model=azure/gpt-5-mini
"""
```

| Option | Default | Description |
|--------|---------|-------------|
| `--llm-model` | `openai/gpt-5-mini` | Model for `llm_assert` semantic assertions |
| `--llm-vision-model` | Falls back to `--llm-model` | Vision model for `llm_assert_image` assertions |
| `--aitest-analysis-prompt` | Built-in prompt | Path to a custom analysis prompt file |
| `--aitest-summary-compact` | Disabled | Omit full conversation turns for passed tests in AI analysis |

## CLI Override

You can override pyproject.toml settings via CLI:

```bash
# Use a different model for this run
pytest tests/ --aitest-summary-model=azure/gpt-5.2-chat

# Different output path
pytest tests/ --aitest-html=custom-report.html

# Run each test 5 times for baseline stability testing
pytest tests/ --aitest-iterations=5

# Custom assertion model
pytest tests/ --llm-model=azure/gpt-5-mini

# Compact AI analysis input for large suites
pytest tests/ --aitest-summary-model=azure/gpt-5.2-chat --aitest-summary-compact
```

## Programmatic Prompt Access

You can retrieve the effective AI analysis prompt (CLI override → hook override → built-in default) in code:

```python
from pytest_aitest import get_analysis_prompt

prompt_text = get_analysis_prompt(pytest_config)
```

To also inspect where it came from:

```python
from pytest_aitest import get_analysis_prompt_details

prompt_text, source, path = get_analysis_prompt_details(pytest_config)
# source: "cli-file" | "hook" | "built-in"
# path: file path when source == "cli-file", otherwise None
```

This is useful for debugging, logging, or tooling that needs to inspect the exact prompt used for AI summary generation.
