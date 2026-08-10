---
description: "A complete CopilotEval example that attaches MCP servers, compares configurations, and generates an HTML report."
---

# Complete example

```python
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
        model="gpt-5.4-mini",
        instructions=system_prompt,
        mcp_servers=BANKING_MCP,
    )

    result = await copilot_eval(agent, "What's my checking balance?")

    assert result.success
    assert result.tool_was_called("get_balance")
```

Run it with:

```bash
uv run python -m pytest tests/test_banking.py -v   --aitest-summary-model=copilot/gpt-5.4-mini   --aitest-html=aitest-reports/report.html
```

This produces a report that compares the two system prompt variants side by side.
