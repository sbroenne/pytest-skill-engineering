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
from pytest_skill_engineering.copilot import CopilotEval

AGENTS = [
    CopilotEval(
        name="banking-v1",
        mcp_servers={"banking": {"command": "python", "args": ["banking_v1.py"]}},
    ),
    CopilotEval(
        name="banking-v2",
        mcp_servers={"banking": {"command": "python", "args": ["banking_v2.py"]}},
    ),
]


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(copilot_eval, agent):
    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
```

This example checks session completion and tool selection only. Also verify the
actual returned values or application state before comparing task success.
pytest shows each test outcome; native JSON records the execution for investigation.

## What to inspect in the evidence

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
async def test_tool_discovery(copilot_eval, agent):
    result = await copilot_eval(agent, "I need to check how much money I have")
    assert result.tool_was_called("get_balance")
```

### Comparing Implementations

Test your server against an open-source alternative:

```python
AGENTS = [
    CopilotEval(
        name="my-implementation",
        mcp_servers={"server": {"command": "python", "args": ["my_server.py"]}},
    ),
    CopilotEval(
        name="reference-implementation",
        mcp_servers={"server": {"command": "npx", "args": ["-y", "@org/reference-server"]}},
    ),
]
```

### Testing Backend Changes

Verify a database migration doesn't affect LLM interactions:

```python
agent_sqlite = CopilotEval(
    name="banking-sqlite",
    mcp_servers={
        "server": {
            "command": "python",
            "args": ["server.py"],
            "env": {"DATABASE_URL": "sqlite:///test.db"},
        }
    },
)

agent_postgres = CopilotEval(
    name="banking-postgres",
    mcp_servers={
        "server": {
            "command": "python",
            "args": ["server.py"],
            "env": {"DATABASE_URL": "postgresql://localhost/test"},
        }
    },
)
```

### Evaluating Schema Changes

Test whether a new input schema is clearer:

```python
# v1: Single "query" parameter
# v2: Separate "account" and "type" parameters


@pytest.mark.parametrize("agent", [agent_v1, agent_v2])
async def test_ambiguous_query(copilot_eval, agent):
    # This query is ambiguous - does the LLM handle it correctly?
    result = await copilot_eval(agent, "How much do I have in checking?")
    assert result.success
```

## Multi-Dimensional Comparison

Test servers across multiple models to find interactions:

```python
MODELS = ["gpt-5.6-sol", "gpt-5.6-luna"]

AGENTS = [
    CopilotEval(
        name=f"banking-{version}-{model}",
        model=model,
        mcp_servers={"banking": {"command": "python", "args": [f"banking_{version}.py"]}},
    )
    for version in ["v1", "v2"]
    for model in MODELS
]

# 2 servers × 2 models = 4 configurations
```

This reveals interactions like:
- "v2 works great with gpt-5.6-luna but fails with gpt-5.6-sol"
- "gpt-5.6-sol needs better tool descriptions to match gpt-5.6-luna performance"

## Investigate the comparison

Inspect captured calls and arguments alongside each server's source and
description. The current coding agent can use the saved evidence to identify
a supported cause and propose one targeted change. There is no report adviser.

Keep the task, model, initial data, limits, and output checks fixed. Parametrized
tests have separate outcomes; `ab_run` pairs have one shared pytest outcome and
need side-specific recorded verification. Repeat representative cases before
claiming a reliability improvement.

## Best Practices

1. **Use the same model** — Isolate the server variable by using the same `model` setting

2. **Test edge cases** — Include ambiguous prompts that stress-test descriptions

3. **Run multiple times** — LLM responses vary; run enough tests to see patterns

4. **Check token usage** — Better descriptions might cost more but improve accuracy

5. **Name servers clearly** — Use descriptive names in saved evidence (`v1`, `v2`, `sqlite`, `postgres`)

## Next Steps

- [Comparing Configurations](comparing.md) — More comparison patterns
- [Inspect Execution Evidence](../how-to/inspect-evidence.md) — Inspect both traces and verification

> 📁 **Real Example:** [copilot/test_10_ab_servers.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_10_ab_servers.py) — Configuration A/B comparison
