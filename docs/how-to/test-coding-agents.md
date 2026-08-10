---
description: "Test real GitHub Copilot coding sessions with CopilotEval, skills, prompt files, and custom agent dispatch."
---

# Test coding agents

Use `CopilotEval` to run real GitHub Copilot sessions inside pytest.

## Quick start

```python
import pytest

from pytest_skill_engineering.copilot import CopilotEval


@pytest.mark.copilot
async def test_creates_module(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="coder",
        model="gpt-5.4-mini",
        instructions="Create production-quality Python code.",
        working_directory=str(tmp_path),
    )

    result = await copilot_eval(
        agent,
        "Create calculator.py with add, subtract, multiply, and divide.",
    )

    assert result.success
    assert result.file_exists("calculator.py")
```

## Core CopilotEval fields

```python
agent = CopilotEval(
    name="my-agent",
    model="gpt-5.4-mini",
    instructions="Your system prompt.",
    working_directory=str(tmp_path),
    max_turns=10,
    max_retries=2,
    excluded_tools=["run_in_terminal"],
    skill_directories=["./skills/my-skill"],
    custom_agents=[],
)
```

## Result helpers

- `result.success`
- `result.error`
- `result.final_response`
- `result.tool_was_called(...)`
- `result.tool_was_called_with(...)`
- `result.file(...)`
- `result.file_exists(...)`
- `result.files_matching(...)`
- `result.subagent_invocations`
- `result.total_premium_requests`

## Custom agents

Attach loaded `.agent.md` definitions to test **custom agent dispatch**:

```python
from pytest_skill_engineering import load_custom_agent


reviewer = load_custom_agent(".github/agents/reviewer.agent.md")

agent = CopilotEval(
    name="orchestrator",
    model="gpt-5.4-mini",
    instructions="Delegate code review requests to the reviewer custom agent.",
    custom_agents=[reviewer],
)
```

The `.agent.md` file defines a **custom agent**. It becomes a **subagent** only when Copilot dispatches to it at runtime. Assert on those runtime events with `result.subagent_invocations`.

## Testing skills

```python
agent = CopilotEval(
    name="with-skill",
    model="gpt-5.4-mini",
    instructions="Use the available skills.",
    skill_directories=["skills/banking-advisor"],
)
```

## Authentication

Supported auth paths:

```bash
gh auth login
```

or `GITHUB_TOKEN` in CI.

## Models

Start with `gpt-5.4-mini` for routine tests. Add larger models only for targeted comparisons.
