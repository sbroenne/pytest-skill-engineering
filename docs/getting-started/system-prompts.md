---
description: "Compare alternative system prompts by varying CopilotEval.instructions and keeping machine identity stable in reports."
---

# System prompts

In pytest-skill-engineering, the **system prompt** is `CopilotEval.instructions`.
The **prompt** is the user message you send into `copilot_eval(...)`.

## Basic pattern

```python
from pytest_skill_engineering.copilot import CopilotEval


agent = CopilotEval(
    name="banking-concise",
    model="gpt-5.4-mini",
    instructions="Be brief. Use the banking tools before answering.",
)
```

## Compare two system prompts

```python
import pytest

from pytest_skill_engineering.copilot import CopilotEval


SYSTEM_PROMPTS = {
    "concise": "Be brief. Use tools before answering.",
    "guided": "Use tools before answering. Explain which account you checked.",
}


@pytest.mark.parametrize("system_prompt_name,system_prompt", SYSTEM_PROMPTS.items())
async def test_balance_prompt(copilot_eval, system_prompt_name, system_prompt):
    agent = CopilotEval(
        name=f"banking-{system_prompt_name}",
        model="gpt-5.4-mini",
        instructions=system_prompt,
    )
    result = await copilot_eval(agent, "What's my checking balance?")

    assert result.success
```

## Naming guidance

Use human-readable `name=` values for report labels.
The report keeps stable machine identity internally and displays these names in the UI.

## Replace vs append

Use `system_message_mode="replace"` only when you want to replace the base Copilot system prompt. Most tests should keep the default append behavior.
