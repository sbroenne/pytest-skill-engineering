---
description: "Compare MCP server variants with a fixed task, model, and output contract."
---

# A/B Testing MCP Servers

Run the same task against two server configurations to investigate a change
to tool descriptions, parameter schemas, response formats, or a backend.
Define the required application result before comparing executions.

## Why A/B Test Servers?

Server descriptions and schemas affect how Copilot discovers and calls tools.
A comparison can reveal a regression for a particular task. It does not
automatically identify its cause or prove that one version is generally better.

## Basic Server Comparison

This **illustrative test** requires your own `my_project.banking_v1` and
`my_project.banking_v2` modules and a `banking_store` fixture. The fixture must
give each test a fresh store, provide its server environment, and expose final
balances independently of Copilot.

```python
from __future__ import annotations

import sys

import pytest

from pytest_skill_engineering.copilot import CopilotEval


@pytest.mark.parametrize("version", ["v1", "v2"])
async def test_transfer(copilot_eval, banking_store, version):
    banking_store.reset(checking=1500, savings=3000)
    agent = CopilotEval(
        name=f"banking-{version}",
        model="gpt-5.6-sol",
        instructions="Use banking tools for account operations.",
        mcp_servers={
            "banking": {
                "command": sys.executable,
                "args": ["-m", f"my_project.banking_{version}"],
                "env": banking_store.server_env,
                "tools": ["*"],
            }
        },
    )
    result = await copilot_eval(agent, "Transfer exactly $100 from checking to savings.")

    assert result.success, result.error
    assert result.evidence_complete, result.capture_errors
    assert banking_store.balances() == {"checking": 1400, "savings": 3100}
```

Each parameter has its own pytest outcome. Adapt the fixture and currency
representation to your application; do not use production accounts.

## What to inspect in the evidence

Inspect calls, arguments, completion flags, operation errors, and actual state
alongside the server source. Tool selection and call counts describe an
execution; they are not correctness checks on their own.

Usage and duration can help investigate differences, subject to missing usage,
model changes, cache effects, and environment variability. Estimated cost needs
explicit [pricing](../how-to/cost-estimation.md).

## Common A/B Testing Scenarios

### Iterating on Tool Descriptions

Change only the description. Keep the task, schema, data, and output check fixed.
Include ambiguous requests only when their expected handling is defined.

### Comparing Implementations

Attach each implementation under the same server key. Initialize equivalent
state and verify the same application requirement, even if tool names differ.
Do not treat matching call sequences as necessary unless the workflow requires
them.

### Testing Backend Changes

Pass test database settings through the server's `env` mapping. Reset each
backend and read the final state through an independent fixture. Separate
working directories do not isolate shared databases.

### Evaluating Schema Changes

Check the completed operation as well as the arguments Copilot chose. A session
that finishes without doing the requested work must still fail the test.

## Multi-Dimensional Comparison

Add a model parameter only after establishing the server comparison. Two
versions, two models, and three repetitions create twelve live executions.
Authorize that cost and verify model access first.

## Investigate the comparison

Keep task, initial state, permissions, limits, and checks fixed. Repeat a
representative case set before making reliability claims. Your coding agent or
a human can investigate likely causes from the source and saved evidence.

With `ab_run`, the two entries share one pytest outcome. Record each side's
verification separately; do not calculate independent per-side pass rates from
that shared outcome. See [Comparing configurations](comparing.md).

## Best Practices

- Change one factor at a time.
- Reset application state for every configuration and repetition.
- Check actual output before interpreting tool or usage differences.
- Name variants clearly and record safe build identifiers.
- Retain failed executions instead of retrying them invisibly.

## Next Steps

- [Test MCP servers](../how-to/test-mcp-servers.md): configure transports and filters.
- [Inspect execution evidence](../how-to/inspect-evidence.md): investigate calls and checks.
