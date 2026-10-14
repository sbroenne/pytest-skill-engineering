---
description: "A CopilotEval example that attaches MCP servers, compares configurations, and records native execution evidence."
---

# Complete example

Save this as `tests/test_banking.py` in an initialized project. It uses the
bundled banking MCP server, so you do not need an external bank or database.
Both variants receive the same task and the same known starting data.

```python
from __future__ import annotations

import json
import sys

import pytest

from pytest_skill_engineering.copilot import CopilotEval


BANKING_MCP = {
    "banking": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
        "tools": ["*"],
    }
}

SYSTEM_PROMPTS = {
    "concise": "Use banking tools before answering. Be brief.",
    "guided": "Use banking tools before answering. Mention which account you checked.",
}


@pytest.mark.parametrize("system_prompt_name,system_prompt", SYSTEM_PROMPTS.items())
async def test_balance(copilot_eval, system_prompt_name, system_prompt):
    agent = CopilotEval(
        name=f"banking-{system_prompt_name}",
        model="gpt-5.6-sol",
        instructions=system_prompt,
        mcp_servers=BANKING_MCP,
    )

    result = await copilot_eval(agent, "Use get_balance to retrieve the checking balance.")

    assert result.success, result.error
    calls = result.tool_calls_for("banking-get_balance")
    assert len(calls) == 1
    assert calls[0].arguments == {"account": "checking"}
    assert calls[0].success is True
    assert calls[0].evidence_complete
    assert calls[0].result is not None
    display, structured = calls[0].result.rsplit("\n\n", 1)
    assert json.loads(structured) == {"result": display}
    observed = json.loads(display)
    assert observed["balance"] == 1500
```

The decoding is specific to this fixture server's string response: the SDK
captures display text and a structured MCP string result. For your own server,
check its actual response format or independent application state.

Run it with:

```bash
uv run python -m pytest tests/test_banking.py -v
```

This makes two live Copilot executions and may consume premium requests.
Use the [getting-started walkthrough](../getting-started/index.md) to configure
authentication, async pytest, and JSON output first.

pytest records a separate outcome for each system prompt variant; JSON captures
each execution. Your coding agent can compare those observations alongside the
source. The test checks returned account data, not the subjective quality of each style.
