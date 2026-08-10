# Migration guide

This project is now centered on **CopilotEval** and GitHub Copilot execution.

## Install

```bash
uv remove pytest-aitest
uv add pytest-skill-engineering
```

## Main migration rules

- replace legacy synthetic/provider setup with `CopilotEval`
- move system prompt text into `instructions=`
- use `name=` for human-readable report labels
- run tests through `copilot_eval(...)`
- attach MCP servers with `mcp_servers={...}`
- load `.agent.md` files with `load_custom_agent()` / `load_custom_agents()`

## Minimal example

```python
from pytest_skill_engineering.copilot import CopilotEval


agent = CopilotEval(
    name="banking-default",
    model="gpt-5.4-mini",
    instructions="Use the banking tools before answering.",
)


async def test_balance(copilot_eval):
    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
```

## Terminology updates

- say **system prompt**, not `system_prompt=` as a separate public API concept
- say **custom agent**, not subagent, for `.agent.md` definitions
- use **subagent** only for runtime dispatch events in results
