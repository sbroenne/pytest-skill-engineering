---
description: "Load .agent.md custom agent definitions into CopilotEval and assert on runtime custom agent dispatch."
---

# Custom agents

A **custom agent** is a `.agent.md` definition file that you load with `load_custom_agent()` or `load_custom_agents()`.

It is **not** inherently a subagent.
It only becomes a **subagent** when Copilot dispatches work to it at runtime.

## Load one custom agent

```python
from pytest_skill_engineering import load_custom_agent
from pytest_skill_engineering.copilot import CopilotEval


reviewer = load_custom_agent(".github/agents/reviewer.agent.md")

agent = CopilotEval(
    name="orchestrator",
    model="gpt-5.4-mini",
    instructions="Delegate code review requests to the reviewer custom agent.",
    custom_agents=[reviewer],
)
```

## Assert on runtime custom agent dispatch

```python
async def test_dispatches_to_reviewer(copilot_eval):
    result = await copilot_eval(agent, "Review src/auth.py for security issues")

    assert result.success
    assert any(invocation.name == "reviewer" for invocation in result.subagent_invocations)
```

`result.subagent_invocations` reports runtime subagent events such as `selected`, `started`, and `completed`.

## Load a directory of custom agents

```python
from pytest_skill_engineering import load_custom_agents


specialists = load_custom_agents(".github/agents", exclude={"orchestrator"})
```

## Compare custom agent variants

```python
import pytest
from pathlib import Path

from pytest_skill_engineering import load_custom_agent
from pytest_skill_engineering.copilot import CopilotEval


AGENT_FILES = sorted(Path(".github/agents").glob("reviewer-*.agent.md"))


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda path: path.stem)
async def test_review_agent_variant(copilot_eval, agent_file):
    reviewer = load_custom_agent(agent_file)
    agent = CopilotEval(
        name=agent_file.stem,
        model="gpt-5.4-mini",
        instructions="Delegate code review tasks to the reviewer custom agent.",
        custom_agents=[reviewer],
    )

    result = await copilot_eval(agent, "Review src/auth.py for security issues")
    assert result.success
```

Use this pattern to validate **custom agent dispatch** with the real Copilot runtime.
