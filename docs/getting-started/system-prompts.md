---
description: "Configure instructions and compare system prompts against fixed output checks."
---

# System prompts

The **system prompt** is `CopilotEval.instructions`: instructions configuring
behavior. The **prompt** is the user task passed to `copilot_eval`. Keep them
separate so the same task can exercise several instruction variants.

## Basic pattern

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="file-writer",
    model="gpt-5.6-sol",
    instructions="Write the requested files. Do not add unrequested fields.",
)
```

## Compare two system prompts

This complete test gives each variant its own workspace and pytest outcome.
It checks the saved JSON, not the assistant's description of it.

```python
from __future__ import annotations

import json

import pytest

from pytest_skill_engineering.copilot import CopilotEval

SYSTEM_PROMPTS = {
    "brief": "Write requested files. Keep the final reply brief.",
    "explain": "Write requested files. Explain what you wrote in the final reply.",
}


@pytest.mark.parametrize("variant,instructions", SYSTEM_PROMPTS.items())
async def test_saved_total(copilot_eval, tmp_path, variant, instructions):
    agent = CopilotEval(
        name=f"total-{variant}",
        model="gpt-5.6-sol",
        instructions=instructions,
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent, "Write total.json containing only the numeric field total, equal to 2 + 3."
    )

    assert result.success, result.error
    assert json.loads((tmp_path / "total.json").read_text(encoding="utf-8")) == {"total": 5}
```

This checks the same task for both variants. It does not measure whether one
reply style is better. Define any additional output criteria before running.

## Naming guidance

Use `name` and pytest parameter IDs to identify variants. JSON saves the
configuration and pytest outcome for each execution. Keep model, tools, initial
state, permissions, and limits fixed; see [Comparing configurations](comparing.md).

## Replace vs append

The default `system_message_mode="append"` adds your instructions to the base
Copilot system prompt. Use `"replace"` only when your test deliberately supplies
the complete system prompt. Replacing instructions does not itself restrict
tools, permissions, or access to external state.
