# API Reference

Quick reference for all types. See linked docs for detailed usage.

## Core Types

### Agent

```python
from pytest_aitest import Agent, Provider

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],           # MCP servers
    cli_servers=[cli],              # CLI servers
    system_prompt="You are...",     # System prompt
    max_turns=10,                   # Max tool-call rounds
)
```

### Provider

```python
from pytest_aitest import Provider

provider = Provider(
    model="azure/gpt-5-mini",       # LiteLLM model string
    temperature=0.7,                # Optional
    max_tokens=1000,                # Optional
)
```

### MCPServer

```python
from pytest_aitest import MCPServer, Wait

server = MCPServer(
    command=["python", "-m", "server"],
    args=["--debug"],               # Optional
    env={"KEY": "value"},           # Optional
    cwd="/path",                    # Optional
    wait=Wait.for_tools(["tool"]),  # Optional
)
```

See **[MCP Server](mcp-server.md)** for details.

### CLIServer

```python
from pytest_aitest import CLIServer

cli = CLIServer(
    name="git-cli",
    command="git",
    tool_prefix="git",              # Creates "git_execute"
    shell="bash",                   # Optional: auto-detect
    cwd="/path",                    # Optional
    env={"KEY": "value"},           # Optional
    discover_help=True,             # Optional: default True
)
```

See **[CLI Server](cli-server.md)** for details.

### Wait

```python
from pytest_aitest import Wait

Wait.ready()                        # Brief startup wait
Wait.for_tools(["tool1", "tool2"])  # Wait for tools
Wait.for_log(r"pattern")            # Wait for log pattern
```

### Prompt

```python
from pytest_aitest import Prompt, load_prompts
from pathlib import Path

prompts = load_prompts(Path("prompts/"))

# YAML format:
# name: MY_PROMPT
# version: "1.0"
# system_prompt: |
#   You are a helpful assistant.
```

### Skill

```python
from pytest_aitest import Skill, load_skill

# Load from directory
skill = Skill.from_path("skills/my-skill")
# Or using helper
skill = load_skill("skills/my-skill")

# Access properties
skill.name               # "my-skill"
skill.description        # From metadata
skill.content            # Instructions prepended to system_prompt
skill.has_references     # True if references/ exists
skill.references         # dict[filename, content]

# Use with Agent
agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    skill=skill,                    # Skill content prepended
    system_prompt="Additional...",  # Your prompt appended
)
```

See **[Skills](skills.md)** for details.

## Fixtures

### aitest_run

Execute an agent with a prompt:

```python
@pytest.mark.asyncio
async def test_example(aitest_run):
    result = await aitest_run(agent, "User prompt here")
    assert result.success
```

### judge

AI-powered semantic assertions:

```python
@pytest.mark.asyncio
async def test_example(aitest_run, judge):
    result = await aitest_run(agent, "Question")
    assert judge(result.final_response, "expected criteria")
```

See **[Assertions](assertions.md)** for details.

### agent_factory

Create agents with defaults:

```python
@pytest.mark.asyncio
async def test_example(agent_factory, aitest_run):
    agent = agent_factory(
        model="azure/gpt-5-mini",
        system_prompt="Be helpful.",
        skill=my_skill,              # Optional
    )
    result = await aitest_run(agent, "Hello")
```

### skill_factory

Load skills from paths:

```python
@pytest.mark.asyncio
async def test_example(skill_factory, agent_factory, aitest_run):
    skill = skill_factory("skills/my-skill")
    agent = agent_factory(skill=skill)
    result = await aitest_run(agent, "Do something")
```

See **[Skills](skills.md)** for details.

## AgentResult

| Property | Type | Description |
|----------|------|-------------|
| `success` | `bool` | Completed without errors |
| `final_response` | `str` | Final text response |
| `turns` | `list[Turn]` | All execution turns |
| `duration_ms` | `int` | Total execution time |
| `token_usage` | `TokenUsage` | Token metrics |
| `cost_usd` | `float` | Estimated cost |
| `error` | `str \| None` | Error if failed |

### Methods

```python
result.tool_was_called("tool")           # Check if called
result.tool_was_called("tool", times=2)  # Exact count
result.tool_call_count("tool")           # Get count
result.tool_call_arg("tool", "param")    # Get argument
result.get_tool_calls("tool")            # Get all calls
```

See **[Assertions](assertions.md)** for details.

## Turn

| Property | Type | Description |
|----------|------|-------------|
| `role` | `str` | "user", "assistant", "tool" |
| `content` | `str` | Message content |
| `tool_calls` | `list[ToolCall]` | Tool calls made |
| `token_usage` | `TokenUsage` | Tokens for turn |

## ToolCall

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Tool name |
| `arguments` | `dict` | Arguments passed |
| `result` | `str` | Tool response |
| `duration_ms` | `int` | Execution time |

## TokenUsage

| Property | Type | Description |
|----------|------|-------------|
| `prompt_tokens` | `int` | Tokens in prompts |
| `completion_tokens` | `int` | Tokens in completions |
| `total_tokens` | `int` | Total tokens |

## CLI Options

| Option | Description |
|--------|-------------|
| `--aitest-model=MODEL` | Model for AI summary |
| `--aitest-html=PATH` | HTML report path |
| `--aitest-json=PATH` | JSON report path |
| `--aitest-summary` | Include AI summary |

See **[Reporting](reporting.md)** for details.
