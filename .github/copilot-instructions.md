# Copilot Instructions for pytest-aitest

## Why This Project Exists

MCP servers and CLIs have two problems nobody talks about:

1. **Design** — Your tool descriptions, parameter names, and error messages are the entire API for LLMs. Getting them right is hard.
2. **Testing** — Traditional tests can't verify if an LLM can actually understand and use your tools.

- **Bad tool description?** The LLM picks the wrong tool.
- **Confusing parameter name?** The LLM passes garbage.
- **Unhelpful error message?** The LLM can't recover.

**The key insight: your test is a prompt.** You write what a user would say ("What's the weather in Paris?"), and the LLM figures out how to use your tools. If it can't, your tool descriptions need work.

## What We're Building

**pytest-aitest** is a pytest plugin for testing MCP servers and CLIs. You write tests as natural language prompts, and an LLM executes them against your tools.

### Core Features

1. **Base Testing**: Define test agents with prompts, run tests against MCP/CLI tool servers
   - Agent = Provider (LLM) + System Prompt + MCP/CLI Servers
   - Use `aitest_run` fixture to execute agent and verify tool usage
   - Assert on `result.success`, `result.tool_was_called("tool_name")`, `result.final_response`

2. **Benchmark Mode** (Model Comparison): Evaluate multiple LLMs against each other
   - Use `@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-4.1"])` 
   - Report auto-detects and shows model comparison table
   - See which model works best for your agent

3. **Arena Mode** (Prompt Comparison): Compare multiple prompts with same model
   - Define prompts in YAML files, load with `load_prompts(Path("prompts/"))`
   - Use `@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)`
   - Report shows prompt comparison table

4. **Matrix Mode**: Full model × prompt grid comparison
   - Combine both parametrize decorators for full matrix
   - Report auto-detects and shows 2D comparison grid

### Adaptive Reporting

Reports **auto-compose** based on detected test dimensions:
- **Simple mode**: Just test list (no parametrize)
- **Model comparison**: Summary + Model table + Test list
- **Prompt comparison**: Summary + Prompt table + Test list  
- **Matrix mode**: Summary + 2D Grid + Model table + Prompt table + Test list

### Key Types

```python
from pytest_aitest import Agent, Provider, MCPServer, Prompt, load_prompts

# Define an agent (auth via AZURE_API_BASE env var)
agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[my_server],
    system_prompt="You are helpful...",
    max_turns=10,
)

# Load YAML prompts
prompts = load_prompts(Path("prompts/"))

# Run test
result = await aitest_run(agent, "Do something with tools")
assert result.success
assert result.tool_was_called("my_tool")
```

### YAML Prompt Format

```yaml
name: PROMPT_EFFICIENT
version: "1.0"
description: Efficient task completion
system_prompt: |
  You are a helpful assistant.
  Complete tasks efficiently with minimal steps.
```

## CRITICAL: Testing Philosophy

**Unit tests with mocks are WORTHLESS for this project.**

This is a testing framework for AI agents. The only way to verify it works is to:
1. Run **real integration tests** against **real LLM providers**
2. Use **actual MCP/CLI servers** that perform real operations
3. Verify the **full pipeline end-to-end**

### What NOT to do:
- Do NOT write unit tests with mocked LLM responses
- Do NOT claim "tests pass" when tests only mock the core functionality
- Do NOT use `unittest.mock.patch` on LiteLLM or agent execution
- Fast test execution (< 1 second) is a RED FLAG - real LLM calls take time

### What TO do:
- Write integration tests that call real Azure OpenAI / OpenAI models
- Use the cheapest available model (check Azure subscription first)
- Test with the Weather or Todo MCP server (built-in test harnesses)
- Verify actual tool calls happen and produce expected results
- Accept that integration tests take 5-30+ seconds per test

## Azure Configuration

**Endpoint**: `https://stbrnner1.cognitiveservices.azure.com/`
**Resource Group**: `rg_foundry`
**Account**: `stbrnner1`

**Authentication**: Entra ID (automatic via `az login`). No API keys needed!
The engine uses `litellm.secret_managers.get_azure_ad_token_provider()` internally.

Available models (checked 2026-02-01):
- `gpt-5-mini` - CHEAPEST, use for most tests
- `gpt-5.1-chat` - More capable
- `gpt-4.1` - Most capable

Check for updates:
```bash
az cognitiveservices account deployment list \
  --name stbrnner1 \
  --resource-group rg_foundry \
  -o table
```

## Project Structure

```
src/pytest_aitest/
├── core/                  # Core types
│   ├── agent.py           # Agent, Provider, MCPServer, CLIServer, Wait
│   ├── prompt.py          # Prompt, load_prompts() for YAML
│   ├── result.py          # AgentResult, Turn, ToolCall
│   └── errors.py          # AITestError, ServerStartError, etc.
├── execution/             # Runtime
│   ├── engine.py          # AgentEngine (LLM loop + tool dispatch)
│   ├── servers.py         # Server process management
│   └── retry.py           # Rate limit retry logic
├── fixtures/              # Pytest fixtures
│   ├── run.py             # aitest_run fixture
│   ├── judge.py           # LLM judge integration
│   └── factories.py       # agent_factory, provider_factory
├── reporting/             # Smart reports
│   ├── collector.py       # Collects test results
│   ├── aggregator.py      # Detects dimensions, groups results
│   ├── generator.py       # Generates HTML/JSON
│   └── renderers/         # Composable report sections
└── testing/               # Test harnesses
    ├── store.py           # KeyValueStore (in-memory)
    └── mcp_server.py      # MCP server wrapping KeyValueStore

tests/
├── integration/           # REAL LLM tests (the only tests that matter)
│   ├── test_agent_integration.py  # Base functionality
│   ├── test_benchmark.py          # Model comparison
│   ├── test_arena.py              # Prompt comparison  
│   ├── test_matrix.py             # Model × Prompt
│   └── prompts/                   # YAML prompt files
└── unit/                  # Pure logic only (no mocking LLMs)
```
