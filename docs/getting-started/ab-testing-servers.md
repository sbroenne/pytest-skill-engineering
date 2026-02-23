---
description: "A/B test MCP server implementations. Compare tool descriptions, parameter schemas, and error handling to find what LLMs understand best."
---

# A/B Testing MCP Servers

Compare different MCP server implementations to find what works best.

## Why A/B Test Servers?

Your MCP server's tool descriptions, schemas, and response formats are the API that LLMs interact with. Small changes can have big impacts:

- Did your refactor break tool discoverability?
- Does the new description improve tool selection?
- Is the v2 output format easier for LLMs to parse?

A/B testing answers these questions with data.

## Basic Server Comparison

Compare two versions of your MCP server:

```python
from pytest_skill_engineering import Eval, Provider, MCPServer

# Two versions to compare
banking_v1 = MCPServer(command=["python", "banking_v1.py"])
banking_v2 = MCPServer(command=["python", "banking_v2.py"])

AGENTS = [
    Eval(
        name="banking-v1",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_v1],
    ),
    Eval(
        name="banking-v2",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_v2],
    ),
]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(eval_run, agent):
    result = await eval_run(agent, "What's my checking balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
```

The report shows which server performs better.

## What the Report Reveals

| Metric | What It Tells You |
|--------|-------------------|
| **Pass rate** | Does the new server break anything? |
| **Tool selection** | Is the LLM picking the right tools? |
| **Tool call count** | Is the new server more efficient? |
| **Token usage** | Does better tool output reduce LLM tokens? |
| **Duration** | Is response time affected? |

## Common A/B Testing Scenarios

### Iterating on Tool Descriptions

Test whether a clearer description improves tool usage:

```python
# v1: Vague description
# get_balance: "Gets balance data"

# v2: Clear description with examples  
# get_balance: "Get current balance for a bank account. Example: get_balance('checking')"

@pytest.mark.parametrize("agent", [agent_v1, agent_v2], ids=["vague", "clear"])
async def test_tool_discovery(eval_run, agent):
    result = await eval_run(agent, "I need to check how much money I have")
    assert result.tool_was_called("get_balance")
```

### Comparing Implementations

Test your server against an open-source alternative:

```python
my_server = MCPServer(command=["python", "my_server.py"])
reference = MCPServer(command=["npx", "-y", "@org/reference-server"])

AGENTS = [
    Eval(name="my-implementation", mcp_servers=[my_server], ...),
    Eval(name="reference-implementation", mcp_servers=[reference], ...),
]
```

### Testing Backend Changes

Verify a database migration doesn't affect LLM interactions:

```python
server_sqlite = MCPServer(
    command=["python", "server.py"],
    env={"DATABASE_URL": "sqlite:///test.db"},
)

server_postgres = MCPServer(
    command=["python", "server.py"],
    env={"DATABASE_URL": "postgresql://localhost/test"},
)
```

### Evaluating Schema Changes

Test whether a new input schema is clearer:

```python
# v1: Single "query" parameter
# v2: Separate "account" and "type" parameters

@pytest.mark.parametrize("agent", [agent_v1, agent_v2])
async def test_ambiguous_query(eval_run, agent):
    # This query is ambiguous - does the LLM handle it correctly?
    result = await eval_run(agent, "How much do I have in checking?")
    assert result.success
```

## Multi-Dimensional Comparison

Test servers across multiple models to find interactions:

```python
MODELS = ["gpt-5-mini", "gpt-4.1"]
SERVERS = {"v1": banking_v1, "v2": banking_v2}

AGENTS = [
    Eval(
        name=f"{server_name}-{model}",
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[server],
    )
    for server_name, server in SERVERS.items()
    for model in MODELS
]

# 2 servers × 2 models = 4 configurations
```

This reveals interactions like:
- "v2 works great with gpt-4.1 but fails with gpt-5-mini"
- "gpt-5-mini needs better tool descriptions to match gpt-4.1 performance"

## AI Insights for Server Comparison

When you run with `--aitest-summary-model`, the report includes:

```
🔧 MCP TOOL FEEDBACK

banking-v1/get_balance — 60% success rate
Current: "Gets balance data"
Issue: LLM often calls get_all_balances instead
Suggested: "Get CURRENT balance for a specific bank account.
            For all accounts at once, use get_all_balances."

banking-v2/get_balance — 95% success rate  
Description is clear and well-targeted.
```

## Best Practices

1. **Use the same model** — Isolate the server variable by using identical providers

2. **Test edge cases** — Include ambiguous prompts that stress-test descriptions

3. **Run multiple times** — LLM responses vary; run enough tests to see patterns

4. **Check token usage** — Better descriptions might cost more but improve accuracy

5. **Name servers clearly** — Use descriptive names that appear in reports (`v1`, `v2`, `sqlite`, `postgres`)

## Next Steps

- [Comparing Configurations](comparing.md) — More comparison patterns
- [Generate Reports](../how-to/generate-reports.md) — Get AI insights on your comparison

> 📁 **Real Example:** [pydantic/test_10_ab_servers.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/pydantic/test_10_ab_servers.py) — Server version comparison and tool description impact testing
